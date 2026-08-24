from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from src.health_memory import HealthMemoryStore
from src.health_memory.database import connect
from src.health_memory.store import digest_payload
from src.serve.coval_health_api import create_app


INGESTION = {
    "member_id": "mom",
    "text": "妈妈今天咳嗽，没有胸痛，也没有喘不上气。晚上记录血压 146/88。",
    "input_mode": "text",
    "event_date": "2026-08-19",
    "source_label": "synthetic unittest note",
    "idempotency_key": "unit-ingest-0001",
}


class HealthMemoryApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "health.sqlite"
        self.client = TestClient(create_app(self.database_path))

    def tearDown(self) -> None:
        self.client.close()
        self.temp_dir.cleanup()

    def test_family_member_crud_round_trip(self) -> None:
        created = self.client.post(
            "/family-members",
            json={
                "id": "aunt",
                "name": "阿姨",
                "relation": "synthetic test member",
                "age": 58,
                "profile": "Only synthetic test data.",
                "badges": ["测试"],
            },
        )
        self.assertEqual(201, created.status_code, created.text)
        updated = self.client.put(
            "/family-members/aunt",
            json={
                "name": "阿姨（已更新）",
                "relation": "synthetic test member",
                "age": 59,
                "profile": "Updated synthetic profile.",
                "badges": ["测试", "已更新"],
            },
        )
        self.assertEqual(200, updated.status_code, updated.text)
        self.assertEqual(59, updated.json()["age"])
        self.assertEqual(204, self.client.delete("/family-members/aunt").status_code)

    def test_family_member_with_history_cannot_be_deleted(self) -> None:
        protected = self.client.post(
            "/family-members",
            json={
                "id": "protected",
                "name": "受保护成员",
                "relation": "synthetic test member",
                "age": 50,
                "profile": "Has synthetic health-memory history.",
                "badges": [],
            },
        )
        self.assertEqual(201, protected.status_code, protected.text)
        protected_ingestion = {
            **INGESTION,
            "member_id": "protected",
            "idempotency_key": "unit-protected-ingest-0001",
        }
        self.assertEqual(201, self.client.post("/ingestions", json=protected_ingestion).status_code)
        blocked = self.client.delete("/family-members/protected")
        self.assertEqual(409, blocked.status_code, blocked.text)
        self.assertEqual("member_has_history", blocked.json()["code"])

    def test_candidate_approval_edit_undo_and_restart(self) -> None:
        ingest = self.client.post("/ingestions", json=INGESTION)
        self.assertEqual(201, ingest.status_code, ingest.text)
        candidate_record = ingest.json()
        record_id = candidate_record["id"]
        self.assertEqual("candidate", candidate_record["status"])
        self.assertEqual("passed", candidate_record["candidate"]["safety"]["state"])
        self.assertEqual([], self.client.get("/timeline", params={"member_id": "mom"}).json())

        candidate = candidate_record["candidate"]
        candidate["summary"] = "家人已核对：咳嗽；否认胸痛和呼吸困难。仅用于复诊沟通。"
        edited = self.client.patch(
            f"/records/{record_id}/candidate",
            json={
                "member_id": "mom",
                "base_candidate_id": candidate_record["candidate_id"],
                "base_candidate_revision": candidate_record["candidate_revision"],
                "candidate": candidate,
                "idempotency_key": "unit-candidate-edit-0001",
            },
        )
        self.assertEqual(200, edited.status_code, edited.text)
        self.assertEqual(2, edited.json()["candidate_revision"])

        approved = self.client.post(
            f"/records/{record_id}/approve",
            json={
                "member_id": "mom",
                "candidate_id": edited.json()["candidate_id"],
                "candidate_revision": edited.json()["candidate_revision"],
                "idempotency_key": "unit-approve-0001",
            },
        )
        self.assertEqual(200, approved.status_code, approved.text)
        v1 = approved.json()["current_version_id"]
        self.assertEqual(1, approved.json()["version_number"])

        snapshot = approved.json()["canonical"]
        snapshot["summary"] = "第二版：补充了连续观察信息；仍不提供诊断或调药建议。"
        v2_response = self.client.patch(
            f"/records/{record_id}",
            json={
                "member_id": "mom",
                "base_version_id": v1,
                "record": snapshot,
                "idempotency_key": "unit-record-edit-0001",
            },
        )
        self.assertEqual(200, v2_response.status_code, v2_response.text)
        v2 = v2_response.json()["current_version_id"]
        self.assertEqual(2, v2_response.json()["version_number"])

        stale = self.client.patch(
            f"/records/{record_id}",
            json={
                "member_id": "mom",
                "base_version_id": v1,
                "record": snapshot,
                "idempotency_key": "unit-stale-edit-0001",
            },
        )
        self.assertEqual(409, stale.status_code)
        self.assertEqual("stale_base_version", stale.json()["code"])

        undone = self.client.post(
            f"/records/{record_id}/undo",
            json={
                "member_id": "mom",
                "base_version_id": v2,
                "target_version_id": v1,
                "idempotency_key": "unit-undo-0001",
            },
        )
        self.assertEqual(200, undone.status_code, undone.text)
        self.assertEqual(3, undone.json()["version_number"])
        self.assertEqual(candidate["summary"], undone.json()["canonical"]["summary"])

        versions = self.client.get(
            f"/records/{record_id}/versions", params={"member_id": "mom"}
        ).json()
        self.assertEqual(["approve", "edit", "undo"], [item["operation"] for item in versions])
        self.assertEqual(3, len({item["id"] for item in versions}))

        restarted = TestClient(create_app(self.database_path))
        try:
            timeline = restarted.get("/timeline", params={"member_id": "mom"}).json()
            self.assertEqual(1, len(timeline))
            self.assertEqual(3, timeline[0]["version_number"])
            record = restarted.get(
                f"/records/{record_id}", params={"member_id": "mom"}
            ).json()
            self.assertEqual(candidate["summary"], record["canonical"]["summary"])
            self.assertEqual("mock-rules-v2", record["extraction"]["extraction_version"])
            self.assertEqual(candidate_record["source"]["sha256"], record["source"]["sha256"])
        finally:
            restarted.close()

    def test_idempotency_duplicate_and_payload_conflict(self) -> None:
        first = self.client.post("/ingestions", json=INGESTION)
        second = self.client.post("/ingestions", json=INGESTION)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertTrue(second.json()["duplicate"])

        changed = {**INGESTION, "text": "不同内容，但错误地复用了相同幂等键。"}
        conflict = self.client.post("/ingestions", json=changed)
        self.assertEqual(409, conflict.status_code)
        self.assertEqual("idempotency_key_reused", conflict.json()["code"])

        same_content_new_key = {**INGESTION, "idempotency_key": "unit-ingest-0002"}
        duplicate = self.client.post("/ingestions", json=same_content_new_key)
        self.assertEqual(first.json()["id"], duplicate.json()["id"])

        with connect(self.database_path) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM source_artifacts").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM health_records").fetchone()[0])

    def test_database_constraints_and_append_only_history(self) -> None:
        record = self.client.post("/ingestions", json=INGESTION).json()
        approved = self.client.post(
            f"/records/{record['id']}/approve",
            json={
                "member_id": "mom",
                "candidate_id": record["candidate_id"],
                "candidate_revision": record["candidate_revision"],
                "idempotency_key": "unit-approve-immutability",
            },
        ).json()
        with connect(self.database_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            required = {
                "family_members", "source_artifacts", "ingestion_jobs", "health_records",
                "record_versions", "observations", "medication_events", "symptom_events",
                "appointments", "reminders", "candidate_safety_events",
                "safety_events", "audit_events",
            }
            self.assertTrue(required.issubset(tables))
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE source_artifacts SET original_text = 'tampered' WHERE id = ?",
                    (record["source"]["id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE record_versions SET edit_reason = 'tampered' WHERE id = ?",
                    (approved["current_version_id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE candidate_safety_events SET safety_state = 'passed' "
                    "WHERE candidate_id = ?",
                    (record["candidate_id"],),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO health_records "
                    "(id, member_id, source_artifact_id, ingestion_job_id, status, created_at, updated_at) "
                    "VALUES ('bad', 'mom', 'missing', 'missing', 'candidate', 'now', 'now')"
                )

    def test_safety_negation_medication_contrast_and_crisis_priority(self) -> None:
        negative = self.client.post(
            "/structure",
            json={"member_id": "mom", "text": "嘴唇颜色正常，无胸痛，也没有喘不上气。"},
        ).json()
        self.assertEqual("passed", negative["safety"])
        self.assertEqual(0, negative["forbidden_advice_generated"])

        coordinated_negative = self.client.post(
            "/structure",
            json={"member_id": "mom", "text": "没有胸闷、胸痛或喘不上气。"},
        ).json()
        self.assertEqual("passed", coordinated_negative["safety"])

        historical_dose = self.client.post(
            "/structure",
            json={"member_id": "dad", "text": "医生让我每天吃两片，帮我记录。"},
        ).json()
        self.assertEqual("passed", historical_dose["safety"])

        request = self.client.post(
            "/structure",
            json={"member_id": "dad", "text": "漏服一次，现在能不能吃两片补回来？"},
        ).json()
        self.assertEqual("refused", request["safety"])
        self.assertTrue(request["unsafe_request_detected"])
        self.assertEqual(0, request["forbidden_advice_generated"])

        crisis = self.client.post(
            "/structure",
            json={"member_id": "mom", "text": "现在喘不上气，能不能把药加倍？"},
        ).json()
        self.assertEqual("escalated", crisis["safety"])

        future_card = self.client.post(
            "/structure",
            json={
                "member_id": "mom",
                "text": "家里人目前都没有不舒服。如果以后喘不上气就联系急救。",
            },
        ).json()
        self.assertEqual("passed", future_card["safety"])

        coordinated_negation = self.client.post(
            "/structure",
            json={
                "member_id": "mom",
                "text": "今天只是颈肩发酸，也没有肢体无力，也没有说话含糊，也没有意识模糊。",
            },
        ).json()
        self.assertEqual("passed", coordinated_negation["safety"])

        sudden_modifier_negation = self.client.post(
            "/structure",
            json={
                "member_id": "mom",
                "text": "今天下午只是颈肩发酸，活动后更明显；没有突然肢体无力，没有说话含糊，也没有意识不清。请整理成一条普通症状记录。",
            },
        ).json()
        self.assertEqual("passed", sudden_modifier_negation["safety"])

        conditional_then_current = self.client.post(
            "/structure",
            json={"member_id": "mom", "text": "如果以后胸痛要联系急救；但我现在确实胸痛。"},
        ).json()
        self.assertEqual("escalated", conditional_then_current["safety"])

        for text in [
            "突然肢体无力。",
            "呼吸越来越困难。",
            "没有发热，胸痛。",
            "无明显诱因出现胸痛。",
            "无缓解的胸痛。",
            "突然胸口压榨样疼，还喘不过气。",
            "突然说话含糊，右边胳膊抬不起来，嘴角歪。",
        ]:
            with self.subTest(text=text):
                response = self.client.post(
                    "/structure", json={"member_id": "mom", "text": text}
                ).json()
                self.assertEqual("escalated", response["safety"])

    def test_candidate_safety_is_immutable_and_candidate_cas_rejects_stale_review(self) -> None:
        crisis_ingestion = {
            **INGESTION,
            "text": "现在呼吸越来越困难，需要马上整理这条 synthetic 记录。",
            "idempotency_key": "unit-crisis-ingest-0001",
        }
        record = self.client.post("/ingestions", json=crisis_ingestion).json()
        downgraded = json.loads(json.dumps(record["candidate"]))
        downgraded["safety"]["state"] = "passed"
        rejected = self.client.patch(
            f"/records/{record['id']}/candidate",
            json={
                "member_id": "mom",
                "base_candidate_id": record["candidate_id"],
                "base_candidate_revision": record["candidate_revision"],
                "candidate": downgraded,
                "idempotency_key": "unit-safety-downgrade-0001",
            },
        )
        self.assertEqual(409, rejected.status_code, rejected.text)
        self.assertEqual("safety_is_server_controlled", rejected.json()["code"])

        edited_candidate = json.loads(json.dumps(record["candidate"]))
        edited_candidate["summary"] = "保留危机升级的 synthetic 家庭复核摘要。"
        edit_a_body = {
            "member_id": "mom",
            "base_candidate_id": record["candidate_id"],
            "base_candidate_revision": record["candidate_revision"],
            "candidate": edited_candidate,
            "idempotency_key": "unit-candidate-cas-0001",
        }
        edited = self.client.patch(
            f"/records/{record['id']}/candidate",
            json=edit_a_body,
        )
        self.assertEqual(200, edited.status_code, edited.text)

        candidate_b = json.loads(json.dumps(edited.json()["candidate"]))
        candidate_b["summary"] = "第二位 reviewer 保存的更新摘要。"
        second_edit = self.client.patch(
            f"/records/{record['id']}/candidate",
            json={
                "member_id": "mom",
                "base_candidate_id": edited.json()["candidate_id"],
                "base_candidate_revision": edited.json()["candidate_revision"],
                "candidate": candidate_b,
                "idempotency_key": "unit-candidate-cas-0002",
            },
        )
        self.assertEqual(200, second_edit.status_code, second_edit.text)

        replay_a = self.client.patch(
            f"/records/{record['id']}/candidate",
            json=edit_a_body,
        )
        self.assertEqual(409, replay_a.status_code, replay_a.text)
        self.assertEqual("stale_candidate", replay_a.json()["code"])

        stale_edit = self.client.patch(
            f"/records/{record['id']}/candidate",
            json={
                "member_id": "mom",
                "base_candidate_id": record["candidate_id"],
                "base_candidate_revision": record["candidate_revision"],
                "candidate": record["candidate"],
                "idempotency_key": "unit-candidate-cas-stale-0001",
            },
        )
        self.assertEqual(409, stale_edit.status_code, stale_edit.text)
        self.assertEqual("stale_candidate", stale_edit.json()["code"])

        stale_approval = self.client.post(
            f"/records/{record['id']}/approve",
            json={
                "member_id": "mom",
                "candidate_id": record["candidate_id"],
                "candidate_revision": record["candidate_revision"],
                "idempotency_key": "unit-candidate-approve-stale-0001",
            },
        )
        self.assertEqual(409, stale_approval.status_code, stale_approval.text)
        self.assertEqual("stale_candidate", stale_approval.json()["code"])

        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT safety_state, origin FROM candidate_safety_events "
                "WHERE record_id = ? ORDER BY created_at, rowid",
                (record["id"],),
            ).fetchall()
        self.assertEqual(
            ["escalated", "escalated", "escalated"],
            [row["safety_state"] for row in rows],
        )
        self.assertEqual(
            ["machine", "carried_forward", "carried_forward"],
            [row["origin"] for row in rows],
        )

    def test_concurrent_database_initialization_is_idempotent(self) -> None:
        database_path = Path(self.temp_dir.name) / "parallel-init.sqlite"

        def initialize(_index: int) -> int:
            return HealthMemoryStore(database_path).schema_version

        with ThreadPoolExecutor(max_workers=10) as pool:
            versions = list(pool.map(initialize, range(10)))
        self.assertEqual({7}, set(versions))
        with connect(database_path) as connection:
            migrations = connection.execute(
                "SELECT version, COUNT(*) AS count FROM schema_migrations GROUP BY version"
            ).fetchall()
            self.assertEqual(
                [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1)],
                [tuple(row) for row in migrations],
            )
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_concurrent_same_ingestion_creates_one_record(self) -> None:
        store = HealthMemoryStore(self.database_path)
        candidate = self.client.post(
            "/structure",
            json={key: value for key, value in INGESTION.items() if key in {"member_id", "text", "input_mode", "event_date"}},
        ).json()["candidate"]
        digest = digest_payload(INGESTION)

        def ingest_once() -> str:
            result = store.ingest_candidate(
                member_id="mom",
                artifact_kind="text",
                source_label=INGESTION["source_label"],
                original_text=INGESTION["text"],
                declared_event_date=INGESTION["event_date"],
                candidate=candidate,
                idempotency_key="concurrent-ingest-0001",
                request_digest=digest,
                provider="mock",
                model_ref="deterministic-safety-rules",
                extraction_version="mock-rules-v2",
                prompt_version="not-applicable",
                contract_version="health-memory-v1",
            )
            return result["id"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            record_ids = list(pool.map(lambda _index: ingest_once(), range(10)))
        self.assertEqual(1, len(set(record_ids)))
        with connect(self.database_path) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM health_records").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
