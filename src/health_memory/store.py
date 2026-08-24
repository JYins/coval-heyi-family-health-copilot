from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .database import apply_migrations, connect, integrity_report, schema_version


class StoreNotFound(RuntimeError):
    pass


class StoreConflict(RuntimeError):
    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message)
        self.code = code


DEMO_MEMBERS = [
    {
        "id": "mom",
        "name": "妈妈",
        "relation": "家庭重点照护",
        "age": 67,
        "profile": "高血压随访中，经常有报告、血压、症状和用药问题需要整理。",
        "badges": ["每日血压", "报告归档", "复诊准备"],
    },
    {
        "id": "dad",
        "name": "爸爸",
        "relation": "用药记录较多",
        "age": 62,
        "profile": "血压、血脂和复诊计划需要长期归档。",
        "badges": ["药物清单", "安全边界", "随访提醒"],
    },
    {
        "id": "self",
        "name": "本人",
        "relation": "个人健康档案",
        "age": 24,
        "profile": "体检、疫苗、过敏和保险材料归档。",
        "badges": ["体检", "疫苗", "保险材料"],
    },
]


class HealthMemoryStore:
    def __init__(self, database_path: Path, seed_demo: bool = True) -> None:
        self.database_path = Path(database_path).resolve()
        self.schema_version = apply_migrations(self.database_path)
        if seed_demo:
            self.seed_demo_members()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def seed_demo_members(self) -> None:
        now = utc_now()
        with self._write() as connection:
            for member in DEMO_MEMBERS:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO family_members
                        (id, name, relation, age, profile, badges_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        member["id"],
                        member["name"],
                        member["relation"],
                        member["age"],
                        member["profile"],
                        compact_json(member["badges"]),
                        now,
                        now,
                    ),
                )

    def list_members(self) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM family_members ORDER BY created_at, id"
            ).fetchall()
        return [_member_dict(row) for row in rows]

    def create_member(self, member: dict[str, Any]) -> dict[str, Any]:
        member_id = member.get("id") or uuid.uuid4().hex
        now = utc_now()
        try:
            with self._write() as connection:
                connection.execute(
                    """
                    INSERT INTO family_members
                        (id, name, relation, age, profile, badges_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        member_id,
                        member["name"],
                        member["relation"],
                        member["age"],
                        member.get("profile", ""),
                        compact_json(member.get("badges", [])),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise StoreConflict("Family member id already exists", "member_exists") from error
        return self.get_member(member_id)

    def get_member(self, member_id: str) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM family_members WHERE id = ?", (member_id,)
            ).fetchone()
        if not row:
            raise StoreNotFound("Family member not found")
        return _member_dict(row)

    def update_member(self, member_id: str, member: dict[str, Any]) -> dict[str, Any]:
        with self._write() as connection:
            cursor = connection.execute(
                """
                UPDATE family_members
                SET name = ?, relation = ?, age = ?, profile = ?, badges_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    member["name"],
                    member["relation"],
                    member["age"],
                    member.get("profile", ""),
                    compact_json(member.get("badges", [])),
                    utc_now(),
                    member_id,
                ),
            )
            if cursor.rowcount != 1:
                raise StoreNotFound("Family member not found")
        return self.get_member(member_id)

    def delete_member(self, member_id: str) -> None:
        try:
            with self._write() as connection:
                cursor = connection.execute("DELETE FROM family_members WHERE id = ?", (member_id,))
                if cursor.rowcount != 1:
                    raise StoreNotFound("Family member not found")
        except sqlite3.IntegrityError as error:
            raise StoreConflict(
                "Family member has health-memory history and cannot be deleted",
                "member_has_history",
            ) from error

    def capture_source(
        self,
        *,
        member_id: str,
        artifact_kind: str,
        source_label: str,
        original_text: str,
        declared_event_date: str | None,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        """Durably store immutable source evidence before any model call."""

        now = utc_now()
        content_digest = sha256_text(original_text)
        with self._write() as connection:
            self._require_member(connection, member_id)
            existing_id = self._idempotent_resource(
                connection, member_id, "capture", idempotency_key, request_digest
            )
            if existing_id:
                result = self._capture_dict(connection, existing_id, member_id)
                result["duplicate"] = True
                return result

            source = connection.execute(
                """
                SELECT id FROM source_artifacts
                WHERE member_id = ? AND artifact_kind = ?
                  AND content_sha256 = ? AND declared_event_date IS ?
                """,
                (member_id, artifact_kind, content_digest, declared_event_date),
            ).fetchone()
            source_id = str(source["id"]) if source else new_id()
            if source is None:
                connection.execute(
                    """
                    INSERT INTO source_artifacts
                        (id, member_id, artifact_kind, source_label, original_text,
                         content_sha256, byte_length, declared_event_date,
                         source_locator_json, captured_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        source_id,
                        member_id,
                        artifact_kind,
                        source_label,
                        original_text,
                        content_digest,
                        len(original_text.encode("utf-8")),
                        declared_event_date,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO source_capture_states
                        (source_artifact_id, member_id, status, created_at, updated_at)
                    VALUES (?, ?, 'captured', ?, ?)
                    """,
                    (source_id, member_id, now, now),
                )
                self._audit(
                    connection,
                    member_id,
                    None,
                    source_id,
                    "source_captured",
                    "local_user",
                    {"artifact_kind": artifact_kind, "content_sha256": content_digest},
                )
            else:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO source_capture_states
                        (source_artifact_id, member_id, status, created_at, updated_at)
                    VALUES (?, ?, 'captured', ?, ?)
                    """,
                    (source_id, member_id, now, now),
                )

            self._save_idempotency(
                connection,
                member_id,
                "capture",
                idempotency_key,
                request_digest,
                "source_artifact",
                source_id,
            )
            result = self._capture_dict(connection, source_id, member_id)
            result["duplicate"] = source is not None
            return result

    def claim_capture(
        self,
        source_artifact_id: str,
        member_id: str,
        *,
        lease_seconds: int = 120,
    ) -> dict[str, Any]:
        """Atomically claim a retryable capture; model inference runs after commit."""

        token = new_id()
        with self._write() as connection:
            # The timestamp must be sampled only after BEGIN IMMEDIATE owns the
            # writer lock. Otherwise time spent waiting for another writer can
            # create an already-expired lease or authorize a stale takeover.
            now = utc_now()
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=max(1, lease_seconds))
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            self._capture_row(connection, source_artifact_id, member_id)
            cursor = connection.execute(
                """
                UPDATE source_capture_states
                SET status = 'processing', attempt_count = attempt_count + 1,
                    last_error_code = NULL, lease_token = ?, lease_expires_at = ?,
                    last_attempt_at = ?, updated_at = ?
                WHERE source_artifact_id = ? AND member_id = ?
                  AND (
                    status IN ('captured', 'failed_retryable')
                    OR (status = 'processing' AND lease_expires_at <= ?)
                  )
                """,
                (
                    token,
                    expires_at,
                    now,
                    now,
                    source_artifact_id,
                    member_id,
                    now,
                ),
            )
            result = self._capture_dict(connection, source_artifact_id, member_id)
            result["claimed"] = cursor.rowcount == 1
            result["lease_token"] = token if cursor.rowcount == 1 else None
            return result

    def mark_capture_failed(
        self,
        source_artifact_id: str,
        member_id: str,
        lease_token: str,
        error_code: str,
    ) -> dict[str, Any]:
        with self._write() as connection:
            cursor = connection.execute(
                """
                UPDATE source_capture_states
                SET status = 'failed_retryable', last_error_code = ?,
                    lease_token = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE source_artifact_id = ? AND member_id = ?
                  AND status = 'processing' AND lease_token = ?
                """,
                (error_code[:80], utc_now(), source_artifact_id, member_id, lease_token),
            )
            if cursor.rowcount != 1:
                current = self._capture_row(connection, source_artifact_id, member_id)
                if current["status"] != "rejected":
                    raise StoreConflict("Capture lease is no longer active", "stale_capture_lease")
            return self._capture_dict(connection, source_artifact_id, member_id)

    def get_capture(self, source_artifact_id: str, member_id: str) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            return self._capture_dict(connection, source_artifact_id, member_id)

    def list_captures(
        self, member_id: str, status: str | None = None
    ) -> list[dict[str, Any]]:
        allowed = {
            "captured", "processing", "failed_retryable", "needs_review", "rejected", "completed"
        }
        if status is not None and status not in allowed:
            raise StoreConflict("Unknown capture status", "invalid_capture_status")
        with connect(self.database_path) as connection:
            self._require_member(connection, member_id)
            if status is None:
                rows = connection.execute(
                    """
                    SELECT source_artifact_id FROM source_capture_states
                    WHERE member_id = ? ORDER BY updated_at DESC, source_artifact_id
                    """,
                    (member_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT source_artifact_id FROM source_capture_states
                    WHERE member_id = ? AND status = ?
                    ORDER BY updated_at DESC, source_artifact_id
                    """,
                    (member_id, status),
                ).fetchall()
            return [
                self._capture_dict(connection, row["source_artifact_id"], member_id)
                for row in rows
            ]

    def reject_capture(
        self, source_artifact_id: str, member_id: str, actor: str = "local_user"
    ) -> dict[str, Any]:
        with self._write() as connection:
            capture = self._capture_row(connection, source_artifact_id, member_id)
            if capture["status"] == "completed":
                raise StoreConflict("Approved history cannot be rejected", "capture_completed")
            if capture["status"] == "rejected":
                return self._capture_dict(connection, source_artifact_id, member_id)
            record_id = capture["record_id"]
            if record_id:
                record = self._record_row(connection, record_id, member_id)
                if record["status"] == "approved":
                    raise StoreConflict("Approved history cannot be rejected", "capture_completed")
                connection.execute(
                    "UPDATE record_candidates SET status = 'rejected' WHERE id = ? AND status = 'pending'",
                    (record["current_candidate_id"],),
                )
                connection.execute(
                    "UPDATE health_records SET status = 'archived', updated_at = ? WHERE id = ?",
                    (utc_now(), record_id),
                )
                connection.execute(
                    "UPDATE ingestion_jobs SET status = 'failed', error_code = 'user_rejected' WHERE id = ?",
                    (record["ingestion_job_id"],),
                )
            now = utc_now()
            connection.execute(
                """
                UPDATE source_capture_states
                SET status = 'rejected', last_error_code = 'user_rejected',
                    lease_token = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE source_artifact_id = ? AND member_id = ?
                """,
                (now, source_artifact_id, member_id),
            )
            self._audit(
                connection,
                member_id,
                record_id,
                source_artifact_id,
                "capture_rejected",
                actor,
                {},
            )
            return self._capture_dict(connection, source_artifact_id, member_id)

    def ingest_candidate(
        self,
        *,
        member_id: str,
        artifact_kind: str,
        source_label: str,
        original_text: str,
        declared_event_date: str | None,
        candidate: dict[str, Any],
        idempotency_key: str,
        request_digest: str,
        provider: str,
        model_ref: str,
        extraction_version: str,
        prompt_version: str,
        contract_version: str,
        source_artifact_id: str | None = None,
        lease_token: str | None = None,
    ) -> dict[str, Any]:
        content_digest = sha256_text(original_text)
        with self._write() as connection:
            # Sample lease time after acquiring the writer lock so lock wait
            # cannot make an expired token appear live at attach time.
            now = utc_now()
            self._require_member(connection, member_id)
            existing_id = self._idempotent_resource(
                connection, member_id, "ingest", idempotency_key, request_digest
            )
            if existing_id:
                result = self._record_dict(connection, existing_id, member_id)
                capture = self._capture_row(
                    connection, str(result["source"]["id"]), member_id
                )
                if capture["status"] == "rejected":
                    raise StoreConflict("Capture was rejected", "capture_rejected")
                result["duplicate"] = True
                return result

            existing = connection.execute(
                """
                SELECT r.id, s.id AS source_artifact_id
                FROM source_artifacts s
                JOIN health_records r ON r.source_artifact_id = s.id
                WHERE s.member_id = ? AND s.artifact_kind = ?
                  AND s.content_sha256 = ? AND s.declared_event_date IS ?
                """,
                (member_id, artifact_kind, content_digest, declared_event_date),
            ).fetchone()
            if existing:
                self._save_idempotency(
                    connection,
                    member_id,
                    "ingest",
                    idempotency_key,
                    request_digest,
                    "health_record",
                    existing["id"],
                )
                result = self._record_dict(connection, existing["id"], member_id)
                result["duplicate"] = True
                return result

            source_id = source_artifact_id or new_id()
            if source_artifact_id is not None:
                source = connection.execute(
                    """
                    SELECT * FROM source_artifacts
                    WHERE id = ? AND member_id = ?
                    """,
                    (source_artifact_id, member_id),
                ).fetchone()
                if not source:
                    raise StoreNotFound("Captured source was not found")
                if (
                    source["artifact_kind"] != artifact_kind
                    or source["source_label"] != source_label
                    or source["original_text"] != original_text
                    or source["content_sha256"] != content_digest
                    or source["declared_event_date"] != declared_event_date
                ):
                    raise StoreConflict(
                        "Captured source does not match ingestion payload",
                        "capture_payload_mismatch",
                    )
                capture = self._capture_row(connection, source_artifact_id, member_id)
                if (
                    capture["status"] != "processing"
                    or not lease_token
                    or capture["lease_token"] != lease_token
                    or capture["lease_expires_at"] is None
                    or capture["lease_expires_at"] <= now
                ):
                    raise StoreConflict(
                        "Capture lease is no longer active",
                        "stale_capture_lease",
                    )
            job_id = new_id()
            record_id = new_id()
            candidate_id = new_id()
            candidate_json = compact_json(candidate)
            if source_artifact_id is None:
                connection.execute(
                    """
                    INSERT INTO source_artifacts
                        (id, member_id, artifact_kind, source_label, original_text,
                         content_sha256, byte_length, declared_event_date,
                         source_locator_json, captured_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        source_id,
                        member_id,
                        artifact_kind,
                        source_label,
                        original_text,
                        content_digest,
                        len(original_text.encode("utf-8")),
                        declared_event_date,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO source_capture_states
                        (source_artifact_id, member_id, status, attempt_count,
                         last_attempt_at, created_at, updated_at)
                    VALUES (?, ?, 'captured', 1, ?, ?, ?)
                    """,
                    (source_id, member_id, now, now, now),
                )
            connection.execute(
                """
                INSERT INTO ingestion_jobs
                    (id, member_id, source_artifact_id, status, provider, model_ref,
                     extraction_version, prompt_version, schema_version, started_at)
                VALUES (?, ?, ?, 'needs_review', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    member_id,
                    source_id,
                    provider,
                    model_ref,
                    extraction_version,
                    prompt_version,
                    contract_version,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO health_records
                    (id, member_id, source_artifact_id, ingestion_job_id, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, 'candidate', ?, ?)
                """,
                (record_id, member_id, source_id, job_id, now, now),
            )
            connection.execute(
                """
                INSERT INTO record_candidates
                    (id, record_id, member_id, source_artifact_id, ingestion_job_id,
                     revision, status, payload_json, payload_sha256,
                     extraction_version, confidence, validation_state, edited_by, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 'pending', ?, ?, ?, 0.55,
                        'machine_candidate', ?, ?)
                """,
                (
                    candidate_id,
                    record_id,
                    member_id,
                    source_id,
                    job_id,
                    candidate_json,
                    sha256_text(candidate_json),
                    extraction_version,
                    f"{provider}_provider",
                    now,
                ),
            )
            connection.execute(
                "UPDATE health_records SET current_candidate_id = ? WHERE id = ?",
                (candidate_id, record_id),
            )
            connection.execute(
                """
                UPDATE source_capture_states
                SET status = 'needs_review', record_id = ?, last_error_code = NULL,
                    lease_token = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE source_artifact_id = ? AND member_id = ?
                """,
                (record_id, now, source_id, member_id),
            )
            self._insert_candidate_safety_event(
                connection,
                member_id=member_id,
                record_id=record_id,
                candidate_id=candidate_id,
                source_artifact_id=source_id,
                safety=candidate["safety"],
                origin="machine",
            )
            self._audit(
                connection,
                member_id,
                record_id,
                source_id,
                "candidate_created",
                f"{provider}_provider",
                {"candidate_revision": 1, "provider": provider},
            )
            self._save_idempotency(
                connection,
                member_id,
                "ingest",
                idempotency_key,
                request_digest,
                "health_record",
                record_id,
            )
            result = self._record_dict(connection, record_id, member_id)
            result["duplicate"] = False
            return result

    def find_idempotent_ingestion(
        self,
        *,
        member_id: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        """Return a completed ingestion retry before expensive inference runs."""

        with connect(self.database_path) as connection:
            existing_id = self._idempotent_resource(
                connection,
                member_id,
                "ingest",
                idempotency_key,
                request_digest,
            )
            if existing_id is None:
                return None
            result = self._record_dict(connection, existing_id, member_id)
            capture = self._capture_row(
                connection, str(result["source"]["id"]), member_id
            )
            if capture["status"] == "rejected":
                raise StoreConflict("Capture was rejected", "capture_rejected")
            result["duplicate"] = True
            return result

    def edit_candidate(
        self,
        *,
        record_id: str,
        member_id: str,
        base_candidate_id: str,
        base_candidate_revision: int,
        candidate: dict[str, Any],
        actor: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        with self._write() as connection:
            existing_candidate_id = self._idempotent_resource(
                connection, member_id, "candidate_edit", idempotency_key, request_digest
            )
            if existing_candidate_id:
                record = self._record_row(connection, record_id, member_id)
                if record["current_candidate_id"] != existing_candidate_id:
                    raise StoreConflict(
                        "The idempotent candidate edit is no longer the current review",
                        "stale_candidate",
                    )
                return self._record_dict(connection, record_id, member_id)

            record = self._record_row(connection, record_id, member_id)
            if record["status"] != "candidate":
                raise StoreConflict("Approved records use the versioned edit route", "already_approved")
            current = self._candidate_row(connection, record["current_candidate_id"], record_id)
            if (
                current["id"] != base_candidate_id
                or int(current["revision"]) != base_candidate_revision
            ):
                raise StoreConflict(
                    "Candidate changed since it was loaded",
                    "stale_candidate",
                )
            current_payload = json.loads(current["payload_json"])
            if candidate.get("safety") != current_payload.get("safety"):
                raise StoreConflict(
                    "Safety findings are server-controlled and cannot be edited",
                    "safety_is_server_controlled",
                )
            revision = int(current["revision"]) + 1
            candidate_id = new_id()
            candidate_json = compact_json(candidate)
            now = utc_now()
            connection.execute(
                "UPDATE record_candidates SET status = 'superseded' WHERE id = ?",
                (current["id"],),
            )
            connection.execute(
                """
                INSERT INTO record_candidates
                    (id, record_id, member_id, source_artifact_id, ingestion_job_id,
                     revision, status, payload_json, payload_sha256,
                     extraction_version, confidence, validation_state, edited_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, 1.0,
                        'user_edited', ?, ?)
                """,
                (
                    candidate_id,
                    record_id,
                    member_id,
                    record["source_artifact_id"],
                    record["ingestion_job_id"],
                    revision,
                    candidate_json,
                    sha256_text(candidate_json),
                    current["extraction_version"],
                    actor,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE health_records
                SET current_candidate_id = ?, updated_at = ?
                WHERE id = ? AND current_candidate_id = ?
                """,
                (candidate_id, now, record_id, base_candidate_id),
            )
            self._insert_candidate_safety_event(
                connection,
                member_id=member_id,
                record_id=record_id,
                candidate_id=candidate_id,
                source_artifact_id=record["source_artifact_id"],
                safety=current_payload["safety"],
                origin="carried_forward",
            )
            self._audit(
                connection,
                member_id,
                record_id,
                record["source_artifact_id"],
                "candidate_edited",
                actor,
                {"candidate_revision": revision},
            )
            self._save_idempotency(
                connection,
                member_id,
                "candidate_edit",
                idempotency_key,
                request_digest,
                "record_candidate",
                candidate_id,
            )
            return self._record_dict(connection, record_id, member_id)

    def approve_candidate(
        self,
        *,
        record_id: str,
        member_id: str,
        candidate_id: str,
        candidate_revision: int,
        actor: str,
        reason: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        with self._write() as connection:
            existing_id = self._idempotent_resource(
                connection, member_id, "approve", idempotency_key, request_digest
            )
            if existing_id:
                return self._record_dict(connection, existing_id, member_id)

            record = self._record_row(connection, record_id, member_id)
            if record["status"] != "candidate":
                raise StoreConflict("Record is already approved", "already_approved")
            candidate = self._candidate_row(connection, record["current_candidate_id"], record_id)
            if candidate["id"] != candidate_id or int(candidate["revision"]) != candidate_revision:
                raise StoreConflict(
                    "Candidate changed since it was loaded",
                    "stale_candidate",
                )
            if candidate["status"] != "pending":
                raise StoreConflict("Current candidate is not pending", "candidate_not_pending")

            version_id = self._insert_version(
                connection,
                record,
                candidate,
                parent_version_id=None,
                version_number=1,
                operation="approve",
                reason=reason,
                actor=actor,
            )
            now = utc_now()
            connection.execute(
                """
                UPDATE record_candidates
                SET status = 'approved', validation_state = 'user_confirmed', approved_at = ?
                WHERE id = ?
                """,
                (now, candidate["id"]),
            )
            connection.execute(
                """
                UPDATE health_records
                SET status = 'approved', current_version_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (version_id, now, record_id),
            )
            connection.execute(
                """
                UPDATE ingestion_jobs SET status = 'completed', completed_at = ?
                WHERE id = ?
                """,
                (now, record["ingestion_job_id"]),
            )
            connection.execute(
                """
                UPDATE source_capture_states
                SET status = 'completed', last_error_code = NULL, updated_at = ?
                WHERE source_artifact_id = ? AND member_id = ?
                """,
                (now, record["source_artifact_id"], member_id),
            )
            self._audit(
                connection,
                member_id,
                record_id,
                record["source_artifact_id"],
                "record_approved",
                actor,
                {"version_id": version_id, "version_number": 1},
            )
            self._save_idempotency(
                connection,
                member_id,
                "approve",
                idempotency_key,
                request_digest,
                "health_record",
                record_id,
            )
            return self._record_dict(connection, record_id, member_id)

    def edit_record(
        self,
        *,
        record_id: str,
        member_id: str,
        base_version_id: str,
        snapshot: dict[str, Any],
        actor: str,
        reason: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        with self._write() as connection:
            existing_id = self._idempotent_resource(
                connection, member_id, "record_edit", idempotency_key, request_digest
            )
            if existing_id:
                return self._record_dict(connection, existing_id, member_id)
            record = self._record_row(connection, record_id, member_id)
            if record["status"] != "approved":
                raise StoreConflict("Candidate must be approved before versioned edits", "not_approved")
            if record["current_version_id"] != base_version_id:
                raise StoreConflict("Record changed since it was loaded", "stale_base_version")
            parent = self._version_row(connection, base_version_id, record_id)
            parent_snapshot = json.loads(parent["snapshot_json"])
            if snapshot.get("safety") != parent_snapshot.get("safety"):
                raise StoreConflict(
                    "Safety findings are server-controlled and cannot be edited",
                    "safety_is_server_controlled",
                )
            candidate = self._insert_user_candidate(connection, record, snapshot, actor)
            version_id = self._insert_version(
                connection,
                record,
                candidate,
                parent_version_id=base_version_id,
                version_number=int(parent["version_number"]) + 1,
                operation="edit",
                reason=reason,
                actor=actor,
            )
            self._advance_head(connection, record, version_id, candidate["id"], actor, "record_edited")
            self._save_idempotency(
                connection,
                member_id,
                "record_edit",
                idempotency_key,
                request_digest,
                "health_record",
                record_id,
            )
            return self._record_dict(connection, record_id, member_id)

    def undo_record(
        self,
        *,
        record_id: str,
        member_id: str,
        base_version_id: str,
        target_version_id: str,
        actor: str,
        reason: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        with self._write() as connection:
            existing_id = self._idempotent_resource(
                connection, member_id, "undo", idempotency_key, request_digest
            )
            if existing_id:
                return self._record_dict(connection, existing_id, member_id)
            record = self._record_row(connection, record_id, member_id)
            if record["current_version_id"] != base_version_id:
                raise StoreConflict("Record changed since it was loaded", "stale_base_version")
            parent = self._version_row(connection, base_version_id, record_id)
            target = self._version_row(connection, target_version_id, record_id)
            snapshot = json.loads(target["snapshot_json"])
            candidate = self._insert_user_candidate(connection, record, snapshot, actor)
            version_id = self._insert_version(
                connection,
                record,
                candidate,
                parent_version_id=base_version_id,
                version_number=int(parent["version_number"]) + 1,
                operation="undo",
                reason=reason,
                actor=actor,
            )
            self._advance_head(
                connection,
                record,
                version_id,
                candidate["id"],
                actor,
                "record_undone",
                {"target_version_id": target_version_id},
            )
            self._save_idempotency(
                connection,
                member_id,
                "undo",
                idempotency_key,
                request_digest,
                "health_record",
                record_id,
            )
            return self._record_dict(connection, record_id, member_id)

    def get_record(self, record_id: str, member_id: str) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            return self._record_dict(connection, record_id, member_id)

    def list_timeline(self, member_id: str) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            self._require_member(connection, member_id)
            rows = connection.execute(
                """
                SELECT r.id, r.current_version_id, v.version_number, v.snapshot_json,
                       v.created_at, s.id AS source_artifact_id, s.source_label,
                       s.content_sha256, j.extraction_version
                FROM health_records r
                JOIN record_versions v ON v.id = r.current_version_id
                JOIN source_artifacts s ON s.id = r.source_artifact_id
                JOIN ingestion_jobs j ON j.id = r.ingestion_job_id
                WHERE r.member_id = ? AND r.status = 'approved'
                ORDER BY COALESCE(json_extract(v.snapshot_json, '$.event_date'), v.created_at) DESC,
                         v.created_at DESC
                """,
                (member_id,),
            ).fetchall()
        return [self._timeline_item(row, member_id) for row in rows]

    def list_versions(self, record_id: str, member_id: str) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            self._record_row(connection, record_id, member_id)
            rows = connection.execute(
                """
                SELECT id, parent_version_id, version_number, operation, snapshot_json,
                       snapshot_sha256, extraction_version, edit_reason, edited_by, created_at
                FROM record_versions WHERE record_id = ? ORDER BY version_number
                """,
                (record_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "snapshot": json.loads(row["snapshot_json"]),
            }
            for row in rows
        ]

    def list_audit_events(self, record_id: str, member_id: str) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            self._record_row(connection, record_id, member_id)
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE record_id = ? ORDER BY created_at, id",
                (record_id,),
            ).fetchall()
        return [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]

    def health(self) -> dict[str, Any]:
        report = integrity_report(self.database_path)
        return {
            "status": "ready" if report == {"integrity": "ok", "foreign_key_errors": 0} else "error",
            "schema_version": schema_version(self.database_path),
            **report,
        }

    def _insert_user_candidate(
        self,
        connection: sqlite3.Connection,
        record: sqlite3.Row,
        snapshot: dict[str, Any],
        actor: str,
    ) -> sqlite3.Row:
        current = self._candidate_row(connection, record["current_candidate_id"], record["id"])
        revision = int(current["revision"]) + 1
        candidate_id = new_id()
        payload_json = compact_json(snapshot)
        now = utc_now()
        connection.execute(
            """
            INSERT INTO record_candidates
                (id, record_id, member_id, source_artifact_id, ingestion_job_id,
                 revision, status, payload_json, payload_sha256, extraction_version,
                 confidence, validation_state, edited_by, created_at, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?, 1.0,
                    'user_confirmed', ?, ?, ?)
            """,
            (
                candidate_id,
                record["id"],
                record["member_id"],
                record["source_artifact_id"],
                record["ingestion_job_id"],
                revision,
                payload_json,
                sha256_text(payload_json),
                current["extraction_version"],
                actor,
                now,
                now,
            ),
        )
        self._insert_candidate_safety_event(
            connection,
            member_id=record["member_id"],
            record_id=record["id"],
            candidate_id=candidate_id,
            source_artifact_id=record["source_artifact_id"],
            safety=snapshot["safety"],
            origin="carried_forward",
        )
        return self._candidate_row(connection, candidate_id, record["id"])

    def _insert_candidate_safety_event(
        self,
        connection: sqlite3.Connection,
        *,
        member_id: str,
        record_id: str,
        candidate_id: str,
        source_artifact_id: str,
        safety: dict[str, Any],
        origin: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO candidate_safety_events
                (id, member_id, record_id, candidate_id, source_artifact_id,
                 safety_state, category, message, unsafe_request_detected,
                 forbidden_advice_generated, origin, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                new_id(),
                member_id,
                record_id,
                candidate_id,
                source_artifact_id,
                safety["state"],
                safety["category"],
                safety["message"],
                int(safety.get("unsafe_request_detected", False)),
                origin,
                utc_now(),
            ),
        )

    def _insert_version(
        self,
        connection: sqlite3.Connection,
        record: sqlite3.Row,
        candidate: sqlite3.Row,
        *,
        parent_version_id: str | None,
        version_number: int,
        operation: str,
        reason: str,
        actor: str,
    ) -> str:
        version_id = new_id()
        now = utc_now()
        connection.execute(
            """
            INSERT INTO record_versions
                (id, record_id, member_id, source_artifact_id, candidate_id,
                 parent_version_id, version_number, operation, snapshot_json,
                 snapshot_sha256, extraction_version, confidence, validation_state,
                 edit_reason, edited_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0,
                    'user_confirmed', ?, ?, ?)
            """,
            (
                version_id,
                record["id"],
                record["member_id"],
                record["source_artifact_id"],
                candidate["id"],
                parent_version_id,
                version_number,
                operation,
                candidate["payload_json"],
                candidate["payload_sha256"],
                candidate["extraction_version"],
                reason,
                actor,
                now,
            ),
        )
        self._insert_projections(
            connection,
            record,
            version_id,
            candidate["extraction_version"],
            json.loads(candidate["payload_json"]),
            now,
        )
        return version_id

    def _insert_projections(
        self,
        connection: sqlite3.Connection,
        record: sqlite3.Row,
        version_id: str,
        extraction_version: str,
        snapshot: dict[str, Any],
        now: str,
    ) -> None:
        shared = (
            record["member_id"],
            record["id"],
            version_id,
            record["source_artifact_id"],
            extraction_version,
        )
        for item in snapshot.get("observations", []):
            connection.execute(
                """
                INSERT INTO observations
                    (id, member_id, record_id, version_id, source_artifact_id,
                     extraction_version, name, value_text, unit, observed_at,
                     confidence, validation_state, source_locator_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'user_confirmed', ?, ?)
                """,
                (new_id(), *shared, item["name"], str(item["value"]), item.get("unit", ""),
                 item.get("observed_at"), compact_json(item.get("source_locator", {})), now),
            )
        for item in snapshot.get("medications", []):
            connection.execute(
                """
                INSERT INTO medication_events
                    (id, member_id, record_id, version_id, source_artifact_id,
                     extraction_version, medication_name, event_type, dose_text,
                     occurred_at, confidence, validation_state, source_locator_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'user_confirmed', ?, ?)
                """,
                (new_id(), *shared, item["name"], item.get("event_type", "reported"),
                 item.get("dose_text", ""), item.get("occurred_at"),
                 compact_json(item.get("source_locator", {})), now),
            )
        for item in snapshot.get("symptoms", []):
            connection.execute(
                """
                INSERT INTO symptom_events
                    (id, member_id, record_id, version_id, source_artifact_id,
                     extraction_version, symptom_text, onset_text, negated,
                     confidence, validation_state, source_locator_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'user_confirmed', ?, ?)
                """,
                (new_id(), *shared, item["text"], item.get("onset_text", ""),
                 int(item.get("negated", False)), compact_json(item.get("source_locator", {})), now),
            )
        for item in snapshot.get("appointments", []):
            connection.execute(
                """
                INSERT INTO appointments
                    (id, member_id, record_id, version_id, source_artifact_id,
                     extraction_version, appointment_text, scheduled_at,
                     confidence, validation_state, source_locator_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'user_confirmed', ?, ?)
                """,
                (new_id(), *shared, item["text"], item.get("scheduled_at"),
                 compact_json(item.get("source_locator", {})), now),
            )
        safety = snapshot["safety"]
        connection.execute(
            """
            INSERT INTO safety_events
                (id, member_id, record_id, version_id, source_artifact_id,
                 safety_state, category, message, unsafe_request_detected,
                 forbidden_advice_generated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                new_id(),
                record["member_id"],
                record["id"],
                version_id,
                record["source_artifact_id"],
                safety["state"],
                safety["category"],
                safety["message"],
                int(safety.get("unsafe_request_detected", False)),
                now,
            ),
        )

    def _advance_head(
        self,
        connection: sqlite3.Connection,
        record: sqlite3.Row,
        version_id: str,
        candidate_id: str,
        actor: str,
        action: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            UPDATE health_records
            SET current_version_id = ?, current_candidate_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (version_id, candidate_id, utc_now(), record["id"]),
        )
        details = {"version_id": version_id}
        details.update(extra or {})
        self._audit(
            connection,
            record["member_id"],
            record["id"],
            record["source_artifact_id"],
            action,
            actor,
            details,
        )

    def _record_dict(
        self, connection: sqlite3.Connection, record_id: str, member_id: str
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT r.*, c.revision AS candidate_revision, c.status AS candidate_status,
                   c.payload_json AS candidate_json, c.validation_state,
                   v.version_number, v.snapshot_json, v.created_at AS version_created_at,
                   s.source_label, s.artifact_kind, s.original_text, s.content_sha256,
                   s.declared_event_date, j.status AS job_status, j.provider,
                   j.model_ref, j.extraction_version, j.prompt_version, j.schema_version
            FROM health_records r
            JOIN record_candidates c ON c.id = r.current_candidate_id
            JOIN source_artifacts s ON s.id = r.source_artifact_id
            JOIN ingestion_jobs j ON j.id = r.ingestion_job_id
            LEFT JOIN record_versions v ON v.id = r.current_version_id
            WHERE r.id = ? AND r.member_id = ?
            """,
            (record_id, member_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Health record not found")
        candidate = json.loads(row["candidate_json"])
        canonical = json.loads(row["snapshot_json"]) if row["snapshot_json"] else None
        return {
            "id": row["id"],
            "member_id": row["member_id"],
            "status": row["status"],
            "candidate_id": row["current_candidate_id"],
            "candidate_revision": row["candidate_revision"],
            "candidate_status": row["candidate_status"],
            "candidate": candidate,
            "current_version_id": row["current_version_id"],
            "version_number": row["version_number"],
            "canonical": canonical,
            "source": {
                "id": row["source_artifact_id"],
                "label": row["source_label"],
                "kind": row["artifact_kind"],
                "original_text": row["original_text"],
                "sha256": row["content_sha256"],
                "event_date": row["declared_event_date"],
            },
            "extraction": {
                "job_id": row["ingestion_job_id"],
                "status": row["job_status"],
                "provider": row["provider"],
                "model_ref": row["model_ref"],
                "extraction_version": row["extraction_version"],
                "prompt_version": row["prompt_version"],
                "schema_version": row["schema_version"],
            },
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _timeline_item(self, row: sqlite3.Row, member_id: str) -> dict[str, Any]:
        snapshot = json.loads(row["snapshot_json"])
        return {
            "id": row["id"],
            "member_id": member_id,
            "date": snapshot.get("event_date") or row["created_at"][:10],
            "title": snapshot["report_type"],
            "detail": snapshot["summary"],
            "tag": row["source_label"],
            "safety": snapshot["safety"]["state"],
            "current_version_id": row["current_version_id"],
            "version_number": row["version_number"],
            "source_artifact_id": row["source_artifact_id"],
            "source_sha256": row["content_sha256"],
            "extraction_version": row["extraction_version"],
        }

    def _record_row(
        self, connection: sqlite3.Connection, record_id: str, member_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM health_records WHERE id = ? AND member_id = ?",
            (record_id, member_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Health record not found")
        return row

    def _capture_row(
        self, connection: sqlite3.Connection, source_artifact_id: str, member_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM source_capture_states
            WHERE source_artifact_id = ? AND member_id = ?
            """,
            (source_artifact_id, member_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Captured source was not found")
        return row

    def _capture_dict(
        self, connection: sqlite3.Connection, source_artifact_id: str, member_id: str
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT c.*, s.artifact_kind, s.source_label, s.original_text,
                   s.content_sha256, s.byte_length, s.declared_event_date, s.captured_at
            FROM source_capture_states c
            JOIN source_artifacts s ON s.id = c.source_artifact_id
            WHERE c.source_artifact_id = ? AND c.member_id = ?
            """,
            (source_artifact_id, member_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Captured source was not found")
        lease_expired = bool(
            row["status"] == "processing"
            and row["lease_expires_at"]
            and row["lease_expires_at"] <= utc_now()
        )
        return {
            "source_artifact_id": row["source_artifact_id"],
            "member_id": row["member_id"],
            "state": row["status"],
            "attempt_count": row["attempt_count"],
            "last_error_code": row["last_error_code"],
            "record_id": row["record_id"],
            "retryable": row["status"] in {"captured", "failed_retryable"} or lease_expired,
            "source": {
                "id": row["source_artifact_id"],
                "kind": row["artifact_kind"],
                "label": row["source_label"],
                "original_text": row["original_text"],
                "sha256": row["content_sha256"],
                "byte_length": row["byte_length"],
                "event_date": row["declared_event_date"],
                "captured_at": row["captured_at"],
            },
            "last_attempt_at": row["last_attempt_at"],
            "lease_expires_at": row["lease_expires_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _candidate_row(
        self, connection: sqlite3.Connection, candidate_id: str, record_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM record_candidates WHERE id = ? AND record_id = ?",
            (candidate_id, record_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Record candidate not found")
        return row

    def _version_row(
        self, connection: sqlite3.Connection, version_id: str, record_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM record_versions WHERE id = ? AND record_id = ?",
            (version_id, record_id),
        ).fetchone()
        if not row:
            raise StoreNotFound("Record version not found")
        return row

    def _require_member(self, connection: sqlite3.Connection, member_id: str) -> None:
        if not connection.execute(
            "SELECT 1 FROM family_members WHERE id = ?", (member_id,)
        ).fetchone():
            raise StoreNotFound("Family member not found")

    def _idempotent_resource(
        self,
        connection: sqlite3.Connection,
        member_id: str,
        operation: str,
        key: str,
        request_digest: str,
    ) -> str | None:
        row = connection.execute(
            """
            SELECT request_sha256, resource_id FROM idempotency_keys
            WHERE member_id = ? AND operation = ? AND idempotency_key = ?
            """,
            (member_id, operation, key),
        ).fetchone()
        if not row:
            return None
        if row["request_sha256"] != request_digest:
            raise StoreConflict(
                "Idempotency key was reused with a different payload",
                "idempotency_key_reused",
            )
        return str(row["resource_id"])

    def _save_idempotency(
        self,
        connection: sqlite3.Connection,
        member_id: str,
        operation: str,
        key: str,
        request_digest: str,
        resource_type: str,
        resource_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO idempotency_keys
                (id, member_id, operation, idempotency_key, request_sha256,
                 resource_type, resource_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id(), member_id, operation, key, request_digest,
             resource_type, resource_id, utc_now()),
        )

    def _audit(
        self,
        connection: sqlite3.Connection,
        member_id: str,
        record_id: str | None,
        source_artifact_id: str | None,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events
                (id, member_id, record_id, source_artifact_id, action,
                 actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id(), member_id, record_id, source_artifact_id,
             action, actor, compact_json(details), utc_now()),
        )


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_payload(value: Any) -> str:
    return sha256_text(compact_json(value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _member_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "relation": row["relation"],
        "age": row["age"],
        "profile": row["profile"],
        "badges": json.loads(row["badges_json"]),
    }
