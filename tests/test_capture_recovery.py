from __future__ import annotations

import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient

from src.health_memory import HealthMemoryStore, StoreConflict
from src.health_memory.database import connect
from src.health_memory.store import digest_payload, utc_now
from src.inference.providers import MockProvider, ProviderOutputError
from src.serve.api_schemas import StructuringRequest
from src.serve.memory_api import create_app


INGESTION = {
    "member_id": "mom",
    "text": "昨晚开始咳嗽，今天体温 37.8 摄氏度。",
    "input_mode": "text",
    "event_date": "2026-08-24",
    "source_label": "合成失败恢复测试",
    "idempotency_key": "capture-recovery-0001",
}


class InvalidOutputProvider(MockProvider):
    def structure(self, payload: StructuringRequest, **_kwargs):  # type: ignore[no-untyped-def]
        del payload
        raise ProviderOutputError("synthetic invalid output")


class CaptureRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "capture.sqlite"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_provider_failure_persists_source_and_restart_retry_succeeds(self) -> None:
        client = TestClient(create_app(self.database_path, provider=InvalidOutputProvider()))
        failed = client.post("/ingestions", json=INGESTION)

        self.assertEqual(202, failed.status_code)
        body = failed.json()
        self.assertEqual("provider_output_invalid", body["error"]["code"])
        self.assertEqual("failed_retryable", body["capture"]["state"])
        self.assertEqual(INGESTION["text"], body["capture"]["source"]["original_text"])
        with connect(self.database_path) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM source_artifacts").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM health_records").fetchone()[0])

        restarted = TestClient(create_app(self.database_path, provider=MockProvider()))
        captures = restarted.get("/ingestions", params={"member_id": "mom"}).json()
        self.assertEqual(1, len(captures))
        retried = restarted.post(
            f"/ingestions/{captures[0]['source_artifact_id']}/retry",
            json={"member_id": "mom"},
        )
        self.assertEqual(200, retried.status_code)
        self.assertEqual("candidate", retried.json()["status"])
        self.assertEqual(INGESTION["text"], retried.json()["source"]["original_text"])
        record = retried.json()
        approved = restarted.post(
            f"/records/{record['id']}/approve",
            json={
                "member_id": "mom",
                "candidate_id": record["candidate_id"],
                "candidate_revision": record["candidate_revision"],
                "idempotency_key": "capture-approve-0001",
            },
        )
        self.assertEqual(200, approved.status_code)
        completed = restarted.get(
            f"/ingestions/{captures[0]['source_artifact_id']}", params={"member_id": "mom"}
        ).json()
        self.assertEqual("completed", completed["state"])
        blocked_retry = restarted.post(
            f"/ingestions/{captures[0]['source_artifact_id']}/retry",
            json={"member_id": "mom"},
        )
        self.assertEqual(409, blocked_retry.status_code)
        self.assertEqual("capture_not_retryable", blocked_retry.json()["code"])

    def test_idempotency_conflict_happens_before_second_model_attempt(self) -> None:
        client = TestClient(create_app(self.database_path, provider=InvalidOutputProvider()))
        self.assertEqual(202, client.post("/ingestions", json=INGESTION).status_code)
        changed = {**INGESTION, "text": "同一个 key 的不同内容"}
        conflict = client.post("/ingestions", json=changed)
        self.assertEqual(409, conflict.status_code)
        self.assertEqual("idempotency_key_reused", conflict.json()["code"])

    def test_concurrent_claim_has_one_winner_and_expired_lease_is_recoverable(self) -> None:
        store = HealthMemoryStore(self.database_path)
        capture = store.capture_source(
            member_id="mom",
            artifact_kind="text",
            source_label=INGESTION["source_label"],
            original_text=INGESTION["text"],
            declared_event_date=INGESTION["event_date"],
            idempotency_key=INGESTION["idempotency_key"],
            request_digest=digest_payload(INGESTION),
        )

        def claim_once(_index: int) -> bool:
            return bool(store.claim_capture(capture["source_artifact_id"], "mom")["claimed"])

        with ThreadPoolExecutor(max_workers=10) as pool:
            winners = list(pool.map(claim_once, range(10)))
        self.assertEqual(1, sum(winners))

        with connect(self.database_path) as connection:
            connection.execute(
                "UPDATE source_capture_states SET lease_expires_at = '2000-01-01T00:00:00.000Z'"
            )
        recovered = store.claim_capture(capture["source_artifact_id"], "mom")
        self.assertTrue(recovered["claimed"])
        self.assertEqual(2, recovered["attempt_count"])

    def test_reject_invalidates_late_provider_result(self) -> None:
        store = HealthMemoryStore(self.database_path)
        capture = store.capture_source(
            member_id="mom",
            artifact_kind="text",
            source_label=INGESTION["source_label"],
            original_text=INGESTION["text"],
            declared_event_date=INGESTION["event_date"],
            idempotency_key=INGESTION["idempotency_key"],
            request_digest=digest_payload(INGESTION),
        )
        claim = store.claim_capture(capture["source_artifact_id"], "mom")
        store.reject_capture(capture["source_artifact_id"], "mom")
        structured = MockProvider().structure(
            StructuringRequest(
                member_id="mom",
                text=INGESTION["text"],
                input_mode="text",
                event_date=INGESTION["event_date"],
            )
        ).response
        inference = structured.inference
        assert inference is not None
        with self.assertRaisesRegex(StoreConflict, "lease"):
            store.ingest_candidate(
                member_id="mom",
                artifact_kind="text",
                source_label=INGESTION["source_label"],
                original_text=INGESTION["text"],
                declared_event_date=INGESTION["event_date"],
                candidate=structured.candidate.model_dump(mode="json"),
                idempotency_key="late-provider-result",
                request_digest=digest_payload({"late": True}),
                provider=inference.provider,
                model_ref=inference.model_ref,
                extraction_version=inference.extraction_version,
                prompt_version=inference.prompt_version,
                contract_version=inference.contract_version,
                source_artifact_id=capture["source_artifact_id"],
                lease_token=claim["lease_token"],
            )
        with connect(self.database_path) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM health_records").fetchone()[0])

    def test_expired_lease_is_retryable_but_old_token_cannot_attach(self) -> None:
        store = HealthMemoryStore(self.database_path)
        capture = store.capture_source(
            member_id="mom",
            artifact_kind="text",
            source_label=INGESTION["source_label"],
            original_text=INGESTION["text"],
            declared_event_date=INGESTION["event_date"],
            idempotency_key=INGESTION["idempotency_key"],
            request_digest=digest_payload(INGESTION),
        )
        claim = store.claim_capture(capture["source_artifact_id"], "mom")
        with connect(self.database_path) as connection:
            connection.execute(
                "UPDATE source_capture_states SET lease_expires_at = '2000-01-01T00:00:00.000Z'"
            )
        expired = store.get_capture(capture["source_artifact_id"], "mom")
        self.assertTrue(expired["retryable"])
        structured = MockProvider().structure(
            StructuringRequest(member_id="mom", text=INGESTION["text"])
        ).response
        inference = structured.inference
        assert inference is not None
        with self.assertRaisesRegex(StoreConflict, "lease"):
            store.ingest_candidate(
                member_id="mom",
                artifact_kind="text",
                source_label=INGESTION["source_label"],
                original_text=INGESTION["text"],
                declared_event_date=INGESTION["event_date"],
                candidate=structured.candidate.model_dump(mode="json"),
                idempotency_key="expired-provider-result",
                request_digest=digest_payload({"expired": True}),
                provider=inference.provider,
                model_ref=inference.model_ref,
                extraction_version=inference.extraction_version,
                prompt_version=inference.prompt_version,
                contract_version=inference.contract_version,
                source_artifact_id=capture["source_artifact_id"],
                lease_token=claim["lease_token"],
            )

    def test_writer_lock_wait_cannot_create_an_already_expired_lease(self) -> None:
        store = HealthMemoryStore(self.database_path)
        capture = store.capture_source(
            member_id="mom",
            artifact_kind="text",
            source_label=INGESTION["source_label"],
            original_text=INGESTION["text"],
            declared_event_date=INGESTION["event_date"],
            idempotency_key=INGESTION["idempotency_key"],
            request_digest=digest_payload(INGESTION),
        )
        started = Event()

        def claim_after_signal() -> dict[str, object]:
            started.set()
            return store.claim_capture(
                capture["source_artifact_id"], "mom", lease_seconds=1
            )

        with connect(self.database_path) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(claim_after_signal)
                self.assertTrue(started.wait(timeout=1))
                time.sleep(1.2)
                blocker.commit()
                claim = future.result(timeout=5)

        self.assertTrue(claim["claimed"])
        self.assertGreater(str(claim["lease_expires_at"]), utc_now())

    def test_lock_wait_cannot_authorize_token_that_expires_before_attach(self) -> None:
        store = HealthMemoryStore(self.database_path)
        capture = store.capture_source(
            member_id="mom",
            artifact_kind="text",
            source_label=INGESTION["source_label"],
            original_text=INGESTION["text"],
            declared_event_date=INGESTION["event_date"],
            idempotency_key=INGESTION["idempotency_key"],
            request_digest=digest_payload(INGESTION),
        )
        claim = store.claim_capture(
            capture["source_artifact_id"], "mom", lease_seconds=1
        )
        structured = MockProvider().structure(
            StructuringRequest(member_id="mom", text=INGESTION["text"])
        ).response
        inference = structured.inference
        assert inference is not None
        started = Event()

        def attach_after_signal() -> dict[str, object]:
            started.set()
            return store.ingest_candidate(
                member_id="mom",
                artifact_kind="text",
                source_label=INGESTION["source_label"],
                original_text=INGESTION["text"],
                declared_event_date=INGESTION["event_date"],
                candidate=structured.candidate.model_dump(mode="json"),
                idempotency_key="lock-wait-provider-result",
                request_digest=digest_payload({"lock_wait": True}),
                provider=inference.provider,
                model_ref=inference.model_ref,
                extraction_version=inference.extraction_version,
                prompt_version=inference.prompt_version,
                contract_version=inference.contract_version,
                source_artifact_id=capture["source_artifact_id"],
                lease_token=claim["lease_token"],
            )

        with connect(self.database_path) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(attach_after_signal)
                self.assertTrue(started.wait(timeout=1))
                time.sleep(1.2)
                blocker.commit()
                with self.assertRaisesRegex(StoreConflict, "lease"):
                    future.result(timeout=5)

    def test_rejected_source_cannot_be_replayed_with_old_or_new_key(self) -> None:
        client = TestClient(create_app(self.database_path, provider=MockProvider()))
        record = client.post("/ingestions", json=INGESTION).json()
        rejected = client.post(
            f"/ingestions/{record['source']['id']}/reject", json={"member_id": "mom"}
        )
        self.assertEqual(200, rejected.status_code)
        replay = client.post("/ingestions", json=INGESTION)
        self.assertEqual(409, replay.status_code)
        self.assertEqual("capture_rejected", replay.json()["code"])
        new_key = client.post(
            "/ingestions", json={**INGESTION, "idempotency_key": "capture-recovery-0002"}
        )
        self.assertEqual(409, new_key.status_code)
        self.assertEqual("capture_rejected", new_key.json()["code"])


if __name__ == "__main__":
    unittest.main()
