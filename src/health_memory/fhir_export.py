from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import connect


FHIR_VERSION = "4.0.1"
_FHIR_NAMESPACE = uuid.UUID("bc706b50-a8c4-4bf8-80bc-5ad91e040e30")


def export_member_document(database_path: Path, member_id: str) -> dict[str, Any]:
    """Export one member's approved current record heads as a FHIR R4 document.

    The export deliberately excludes pending candidates. It is a portable mapping,
    not a claim of conformance to a regional implementation guide.
    """

    with connect(database_path) as connection:
        member = connection.execute(
            "SELECT id, name FROM family_members WHERE id = ?", (member_id,)
        ).fetchone()
        if member is None:
            raise ValueError(f"Family member not found: {member_id}")
        records = connection.execute(
            """
            SELECT r.id AS record_id, r.current_version_id, v.snapshot_json,
                   v.created_at AS version_created_at, s.id AS source_id,
                   s.source_label, s.artifact_kind, s.original_text,
                   s.content_sha256, s.byte_length, s.declared_event_date
            FROM health_records r
            JOIN record_versions v ON v.id = r.current_version_id
            JOIN source_artifacts s ON s.id = r.source_artifact_id
            WHERE r.member_id = ? AND r.status = 'approved'
            ORDER BY COALESCE(json_extract(v.snapshot_json, '$.event_date'), v.created_at),
                     v.created_at, r.id
            """,
            (member_id,),
        ).fetchall()

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    patient_id = _stable_id("Patient", member_id)
    device_id = _stable_id("Device", "coval-health")
    composition_id = _stable_id("Composition", f"{member_id}:{timestamp}")
    entries: list[dict[str, Any]] = []

    composition = {
        "resourceType": "Composition",
        "id": composition_id,
        "status": "final",
        "type": {"text": "家庭健康纵向记录导出"},
        "subject": {"reference": _reference(patient_id)},
        "date": timestamp,
        "author": [{"reference": _reference(device_id)}],
        "title": f"{member['name']}的家庭健康记录",
        "confidentiality": "R",
        "section": [],
    }
    entries.append(_entry(composition))
    entries.append(
        _entry(
            {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [
                    {"system": "urn:coval-health:family-member", "value": member_id}
                ],
                "name": [{"text": member["name"]}],
            }
        )
    )
    entries.append(
        _entry(
            {
                "resourceType": "Device",
                "id": device_id,
                "status": "active",
                "deviceName": [{"name": "Coval Health Memory", "type": "user-friendly-name"}],
            }
        )
    )

    for row in records:
        snapshot = json.loads(row["snapshot_json"])
        record_refs: list[dict[str, str]] = []
        document_id = _stable_id("DocumentReference", row["source_id"])
        document = {
            "resourceType": "DocumentReference",
            "id": document_id,
            "identifier": [
                {"system": "urn:coval-health:source-sha256", "value": row["content_sha256"]}
            ],
            "status": "current",
            "type": {"text": row["artifact_kind"]},
            "subject": {"reference": _reference(patient_id)},
            "date": row["version_created_at"],
            "description": row["source_label"],
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain; charset=utf-8",
                        "data": base64.b64encode(row["original_text"].encode("utf-8")).decode(
                            "ascii"
                        ),
                        "size": row["byte_length"],
                        "title": row["source_label"],
                    }
                }
            ],
        }
        entries.append(_entry(document))
        record_refs.append({"reference": _reference(document_id)})

        effective = _fhir_datetime(snapshot.get("event_date") or row["declared_event_date"])
        for index, observation in enumerate(snapshot.get("observations", [])):
            resource = {
                "resourceType": "Observation",
                "id": _stable_id(
                    "Observation", f"{row['record_id']}:{row['current_version_id']}:observation:{index}"
                ),
                "status": "final",
                "code": {"text": observation["name"]},
                "subject": {"reference": _reference(patient_id)},
                "derivedFrom": [{"reference": _reference(document_id)}],
                "valueString": _observation_value(observation),
            }
            _set_if(resource, "effectiveDateTime", _fhir_datetime(observation.get("observed_at")) or effective)
            entries.append(_entry(resource))
            record_refs.append({"reference": _reference(resource["id"])})

        for index, symptom in enumerate(snapshot.get("symptoms", [])):
            resource = {
                "resourceType": "Observation",
                "id": _stable_id(
                    "Observation", f"{row['record_id']}:{row['current_version_id']}:symptom:{index}"
                ),
                "status": "final",
                "category": [{"text": "symptom"}],
                "code": {"text": symptom["text"]},
                "subject": {"reference": _reference(patient_id)},
                "derivedFrom": [{"reference": _reference(document_id)}],
                "valueBoolean": not bool(symptom.get("negated")),
            }
            _set_if(resource, "effectiveDateTime", effective)
            if symptom.get("onset_text"):
                resource["note"] = [{"text": f"起始描述：{symptom['onset_text']}"}]
            entries.append(_entry(resource))
            record_refs.append({"reference": _reference(resource["id"])})

        for index, medication in enumerate(snapshot.get("medications", [])):
            resource = {
                "resourceType": "MedicationStatement",
                "id": _stable_id(
                    "MedicationStatement",
                    f"{row['record_id']}:{row['current_version_id']}:{index}",
                ),
                "status": _medication_status(medication.get("event_type")),
                "medicationCodeableConcept": {"text": medication["name"]},
                "subject": {"reference": _reference(patient_id)},
                "derivedFrom": [{"reference": _reference(document_id)}],
            }
            _set_if(
                resource,
                "effectiveDateTime",
                _fhir_datetime(medication.get("occurred_at")) or effective,
            )
            if medication.get("dose_text"):
                resource["dosage"] = [{"text": medication["dose_text"]}]
            entries.append(_entry(resource))
            record_refs.append({"reference": _reference(resource["id"])})

        for index, allergy in enumerate(snapshot.get("allergies", [])):
            resource = {
                "resourceType": "AllergyIntolerance",
                "id": _stable_id(
                    "AllergyIntolerance",
                    f"{row['record_id']}:{row['current_version_id']}:{index}",
                ),
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            "code": "unconfirmed",
                        }
                    ]
                },
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                        }
                    ]
                },
                "patient": {"reference": _reference(patient_id)},
                "code": {"text": allergy},
                "note": [
                    {
                        "text": (
                            f"家庭记录，尚未由临床人员核实。来源：DocumentReference/{document_id}"
                        )
                    }
                ],
            }
            _set_if(resource, "recordedDate", effective)
            entries.append(_entry(resource))
            record_refs.append({"reference": _reference(resource["id"])})

        for index, appointment in enumerate(snapshot.get("appointments", [])):
            resource = {
                "resourceType": "Appointment",
                "id": _stable_id(
                    "Appointment", f"{row['record_id']}:{row['current_version_id']}:{index}"
                ),
                "status": "proposed",
                "description": appointment["text"],
                "participant": [
                    {"actor": {"reference": _reference(patient_id)}, "status": "needs-action"}
                ],
                "supportingInformation": [
                    {"reference": _reference(document_id)}
                ],
            }
            scheduled = _fhir_datetime(appointment.get("scheduled_at"))
            if scheduled:
                resource["comment"] = f"计划时间：{scheduled}"
            entries.append(_entry(resource))
            record_refs.append({"reference": _reference(resource["id"])})

        composition["section"].append(
            {
                "title": snapshot["report_type"],
                "text": {
                    "status": "generated",
                    "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\"><p>{_xml_escape(snapshot['summary'])}</p></div>",
                },
                "entry": record_refs,
            }
        )
    if not composition["section"]:
        composition["section"] = [
            {
                "title": "当前无已确认记录",
                "text": {
                    "status": "generated",
                    "div": '<div xmlns="http://www.w3.org/1999/xhtml"><p>当前无已确认记录。</p></div>',
                },
            }
        ]

    return {
        "resourceType": "Bundle",
        "id": _stable_id("Bundle", f"{member_id}:{timestamp}"),
        "meta": {"tag": [{"system": "urn:coval-health", "code": "synthetic-or-local-export"}]},
        "identifier": {
            "system": "urn:coval-health:fhir-document",
            "value": str(uuid.uuid5(_FHIR_NAMESPACE, f"bundle:{member_id}:{timestamp}")),
        },
        "type": "document",
        "timestamp": timestamp,
        "entry": entries,
    }


def _entry(resource: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullUrl": f"urn:uuid:{resource['id']}",
        "resource": resource,
    }


def _reference(resource_id: str) -> str:
    return f"urn:uuid:{resource_id}"


def _stable_id(resource_type: str, value: str) -> str:
    return str(uuid.uuid5(_FHIR_NAMESPACE, f"{resource_type}:{value}"))


def _fhir_datetime(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        if len(candidate) == 10:
            datetime.fromisoformat(candidate)
            return candidate
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return candidate
    except ValueError:
        return None


def _medication_status(event_type: object) -> str:
    return {
        "stopped": "stopped",
        "missed": "not-taken",
    }.get(str(event_type), "unknown")


def _observation_value(observation: dict[str, Any]) -> str:
    value = str(observation["value"])
    unit = str(observation.get("unit") or "").strip()
    return f"{value} {unit}".strip()


def _set_if(resource: dict[str, Any], key: str, value: object) -> None:
    if value is not None:
        resource[key] = value


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
