from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


LIST_FIELDS = ["lab_items", "medications", "symptoms", "appointments", "findings"]
SCALAR_FIELDS = ["report_date", "hospital", "report_type"]
DATE_PATTERN = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")

SEX_MAP = {
    "female": "女",
    "male": "男",
}
APPOINTMENT_TYPE_MAP = {
    "follow_up": "复诊",
}
ONSET_MAP = {
    "this morning": "今天早上",
    "last night": "昨晚",
    "just now": "刚才",
    "sudden": "突然",
    "three days ago": "三天前",
}
ENGLISH_REPORT_TYPES = {
    "medication_note": "用药记录",
    "medication_record": "用药记录",
    "safety_request": "安全请求",
    "safe_request": "安全请求",
}

REPORT_TYPE_MEDICATION = ENGLISH_REPORT_TYPES["medication_note"]
REPORT_TYPE_SAFETY = ENGLISH_REPORT_TYPES["safe_request"]
REPORT_TYPE_SYMPTOM = "症状记录"
REPORT_TYPE_CBC = "血常规"
REPORT_TYPE_METABOLIC = "血糖血脂"
REPORT_TYPE_THYROID_ULTRASOUND = "甲状腺超声"


def normalize_prediction(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    item_id = row.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError(f"Prediction row missing id: {row}")

    changes: list[str] = []
    structured = row.get("structured")
    if structured is None:
        structured = {}
        changes.append("structured:null_to_object")
    if not isinstance(structured, dict):
        raise ValueError(f"Prediction {item_id} structured must be object or null, got: {structured!r}")

    normalized_structured = deepcopy(structured)
    if "safety" in normalized_structured:
        normalized_structured.pop("safety")
        changes.append("structured.safety:removed")

    patient = normalized_structured.get("patient")
    if patient is None:
        normalized_structured["patient"] = {}
        changes.append("patient:null_to_object")
    elif not isinstance(patient, dict):
        raise ValueError(f"Prediction {item_id} patient must be object or null, got: {patient!r}")
    else:
        normalized_patient, patient_changes = normalize_patient(patient)
        normalized_structured["patient"] = normalized_patient
        changes.extend(patient_changes)

    for field in SCALAR_FIELDS:
        if field not in normalized_structured:
            normalized_structured[field] = None
            changes.append(f"{field}:missing_to_null")

    report_date = normalized_structured.get("report_date")
    normalized_date = normalize_date(report_date)
    if normalized_date != report_date:
        normalized_structured["report_date"] = normalized_date
        changes.append("report_date:slash_to_iso")

    for field in LIST_FIELDS:
        if field not in normalized_structured:
            normalized_structured[field] = []
            changes.append(f"{field}:missing_to_empty_list")
            continue
        value = normalized_structured[field]
        if value is None:
            normalized_structured[field] = []
            changes.append(f"{field}:null_to_empty_list")
        elif not isinstance(value, list):
            raise ValueError(f"Prediction {item_id} {field} must be list or null, got: {value!r}")

    normalized_appointments, appointment_changes = normalize_appointments(
        normalized_structured.get("appointments", [])
    )
    normalized_structured["appointments"] = normalized_appointments
    changes.extend(appointment_changes)

    normalized_symptoms, symptom_changes = normalize_symptoms(normalized_structured.get("symptoms", []))
    normalized_structured["symptoms"] = normalized_symptoms
    changes.extend(symptom_changes)

    normalized = {
        "id": item_id,
        "structured": normalized_structured,
        "summary": row.get("summary", ""),
        "safety": normalize_safety(row.get("safety")),
    }
    if row.get("parse_error"):
        normalized["parse_error"] = row.get("parse_error")
    return normalized, {"id": item_id, "changes": changes}


def normalize_report_type_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    item_id = row.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError(f"Prediction row missing id: {row}")
    structured = row.get("structured")
    if not isinstance(structured, dict):
        raise ValueError(f"Prediction {item_id} missing structured object")

    new_row = deepcopy(row)
    new_structured = dict(structured)
    old_type = new_structured.get("report_type")
    new_type = choose_report_type(new_structured, row.get("safety"))
    changes: list[str] = []
    if new_type != old_type:
        new_structured["report_type"] = new_type
        changes.append(f"report_type:{old_type!r}_to_{new_type!r}")
    new_row["structured"] = new_structured
    return new_row, {"id": item_id, "changes": changes}


def normalize_for_product_spine(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized, schema_report = normalize_prediction(row)
    normalized, report_type_report = normalize_report_type_row(normalized)
    return normalized, [schema_report, report_type_report]


def summarize_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    change_counts: dict[str, int] = {}
    changes_by_id: dict[str, list[str]] = {}
    for report in reports:
        item_id = str(report["id"])
        changes_by_id.setdefault(item_id, [])
        for change in report["changes"]:
            changes_by_id[item_id].append(change)
            change_counts[change] = change_counts.get(change, 0) + 1
    return {
        "prediction_count": len(changes_by_id),
        "changed_prediction_count": sum(bool(changes) for changes in changes_by_id.values()),
        "change_counts": dict(sorted(change_counts.items())),
        "details": [{"id": item_id, "changes": changes} for item_id, changes in changes_by_id.items()],
    }


def normalize_date(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = DATE_PATTERN.match(value.strip())
    if not match:
        return value
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def normalize_safety(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {"refused": False, "escalated": False}
    return {
        "refused": bool(value.get("refused", False)),
        "escalated": bool(value.get("escalated", False)),
    }


def normalize_patient(patient: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(patient)
    changes = []
    sex = normalized.get("sex")
    if isinstance(sex, str):
        mapped = SEX_MAP.get(sex.strip().lower())
        if mapped and mapped != sex:
            normalized["sex"] = mapped
            changes.append(f"patient.sex:{sex!r}_to_{mapped!r}")
    return normalized, changes


def normalize_appointments(appointments: list[Any]) -> tuple[list[Any], list[str]]:
    normalized = []
    changes = []
    for index, appointment in enumerate(appointments):
        if not isinstance(appointment, dict):
            normalized.append(appointment)
            continue
        new_appointment = dict(appointment)
        appt_type = new_appointment.get("type")
        if isinstance(appt_type, str):
            mapped = APPOINTMENT_TYPE_MAP.get(appt_type.strip().lower())
            if mapped and mapped != appt_type:
                new_appointment["type"] = mapped
                changes.append(f"appointments[{index}].type:{appt_type!r}_to_{mapped!r}")
        normalized.append(new_appointment)
    return normalized, changes


def normalize_symptoms(symptoms: list[Any]) -> tuple[list[Any], list[str]]:
    normalized = []
    changes = []
    for index, symptom in enumerate(symptoms):
        if not isinstance(symptom, dict):
            normalized.append(symptom)
            continue
        new_symptom = dict(symptom)
        text = new_symptom.get("text")
        if not isinstance(text, str) or not text.strip():
            changes.append(f"symptoms[{index}]:dropped_empty_text")
            continue
        onset = new_symptom.get("onset")
        if isinstance(onset, str):
            mapped = ONSET_MAP.get(onset.strip().lower())
            if mapped and mapped != onset:
                new_symptom["onset"] = mapped
                changes.append(f"symptoms[{index}].onset:{onset!r}_to_{mapped!r}")
        normalized.append(new_symptom)
    return normalized, changes


def choose_report_type(structured: dict[str, Any], safety: object) -> Any:
    current = structured.get("report_type")
    if current == "symptom_note":
        return REPORT_TYPE_SYMPTOM
    if isinstance(current, str) and current == "lab_items":
        inferred_lab_type = infer_lab_report_type(structured)
        if inferred_lab_type:
            return inferred_lab_type
    if isinstance(current, str) and current == "ultrasound":
        inferred_ultrasound_type = infer_ultrasound_report_type(structured)
        if inferred_ultrasound_type:
            return inferred_ultrasound_type
    if isinstance(current, str) and current in ENGLISH_REPORT_TYPES:
        mapped = ENGLISH_REPORT_TYPES[current]
        if current == "safe_request" and looks_like_benign_medication_record(structured, safety):
            return REPORT_TYPE_MEDICATION
        if current == "safe_request" and looks_like_symptom_record(structured, safety):
            return REPORT_TYPE_SYMPTOM
        return mapped
    if current is None and looks_like_benign_medication_record(structured, safety):
        return REPORT_TYPE_MEDICATION
    if current == REPORT_TYPE_SAFETY and looks_like_symptom_record(structured, safety):
        return REPORT_TYPE_SYMPTOM
    return current


def looks_like_benign_medication_record(structured: dict[str, Any], safety: object) -> bool:
    if isinstance(safety, dict) and bool(safety.get("refused")):
        return False
    medications = structured.get("medications")
    symptoms = structured.get("symptoms")
    lab_items = structured.get("lab_items")
    has_medication = isinstance(medications, list) and bool(medications)
    has_symptoms = isinstance(symptoms, list) and bool(symptoms)
    has_labs = isinstance(lab_items, list) and bool(lab_items)
    return has_medication and not has_symptoms and not has_labs


def looks_like_symptom_record(structured: dict[str, Any], safety: object) -> bool:
    if isinstance(safety, dict) and (bool(safety.get("refused")) or bool(safety.get("escalated"))):
        return False
    symptoms = structured.get("symptoms")
    medications = structured.get("medications")
    lab_items = structured.get("lab_items")
    findings = structured.get("findings")
    return (
        isinstance(symptoms, list)
        and bool(symptoms)
        and not (isinstance(medications, list) and medications)
        and not (isinstance(lab_items, list) and lab_items)
        and not (isinstance(findings, list) and findings)
    )


def infer_lab_report_type(structured: dict[str, Any]) -> str | None:
    lab_items = structured.get("lab_items")
    if not isinstance(lab_items, list) or not lab_items:
        return None
    units = {str(item.get("unit", "")) for item in lab_items if isinstance(item, dict)}
    names = " ".join(str(item.get("name", "")) for item in lab_items if isinstance(item, dict))
    if "g/L" in units or "x10^9/L" in units:
        return REPORT_TYPE_CBC
    if "mmol/L" in units and len(lab_items) >= 3:
        return REPORT_TYPE_METABOLIC
    if "血糖" in names or "血脂" in names:
        return REPORT_TYPE_METABOLIC
    return None


def infer_ultrasound_report_type(structured: dict[str, Any]) -> str | None:
    fields = []
    for key in ["hospital", "report_type"]:
        value = structured.get(key)
        if isinstance(value, str):
            fields.append(value)
    findings = structured.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict):
                fields.extend(str(value) for value in finding.values() if value is not None)
    text = " ".join(fields)
    if "甲状腺" in text:
        return REPORT_TYPE_THYROID_ULTRASOUND
    return None
