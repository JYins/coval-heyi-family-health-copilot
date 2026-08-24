from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from src.health_memory import HealthMemoryStore
from src.health_memory.fhir_export import _fhir_datetime, _medication_status
from src.health_memory.database import connect
from src.health_memory.vault import (
    VaultError,
    _install_temporary,
    _temporary_sibling,
    create_backup,
    restore_backup,
    verify_backup,
)
from src.serve.coval_health_api import create_app


class VaultBackupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "source" / "health.sqlite"
        self.client = TestClient(create_app(self.database, seed_demo=True))
        ingestion = self.client.post(
            "/ingestions",
            json={
                "member_id": "mom",
                "text": "合成记录：2026年8月20日血压 146/88，无胸痛。医生此前记录继续观察。",
                "input_mode": "text",
                "event_date": "2026-08-20",
                "source_label": "synthetic vault fixture",
                "idempotency_key": "vault-ingestion-0001",
            },
        )
        self.assertEqual(201, ingestion.status_code, ingestion.text)
        candidate = ingestion.json()
        candidate_payload = candidate["candidate"]
        candidate_payload["medications"] = [
            {
                "name": "氨氯地平",
                "event_type": "reported",
                "dose_text": "家庭记录：每日一片",
                "occurred_at": None,
                "source_locator": {"start": 30, "end": 34},
            }
        ]
        candidate_payload["allergies"] = ["青霉素（家庭记录，待医生核对）"]
        edited = self.client.patch(
            f"/records/{candidate['id']}/candidate",
            json={
                "member_id": "mom",
                "base_candidate_id": candidate["candidate_id"],
                "base_candidate_revision": candidate["candidate_revision"],
                "candidate": candidate_payload,
                "idempotency_key": "vault-candidate-edit-0001",
            },
        )
        self.assertEqual(200, edited.status_code, edited.text)
        approval = self.client.post(
            f"/records/{candidate['id']}/approve",
            json={
                "member_id": "mom",
                "candidate_id": edited.json()["candidate_id"],
                "candidate_revision": edited.json()["candidate_revision"],
                "idempotency_key": "vault-approval-0001",
            },
        )
        self.assertEqual(200, approval.status_code, approval.text)
        self.record_id = candidate["id"]

    def tearDown(self) -> None:
        self.client.close()
        self.temp_dir.cleanup()

    def test_backup_verify_restore_and_fhir_round_trip(self) -> None:
        archive = self.root / "backup" / "family.coval"
        manifest = create_backup(self.database, archive)

        self.assertEqual("coval-health-vault", manifest["format"])
        self.assertEqual("none", manifest["encryption"])
        self.assertIn("database.sqlite", manifest["files"])
        self.assertIn("exports/fhir-r4/mom.json", manifest["files"])
        verified = verify_backup(archive)
        self.assertTrue(verified["verified"])

        with zipfile.ZipFile(archive, "r") as package:
            bundle = json.loads(package.read("exports/fhir-r4/mom.json"))
        self.assertEqual("Bundle", bundle["resourceType"])
        self.assertEqual("document", bundle["type"])
        self.assertEqual("Composition", bundle["entry"][0]["resource"]["resourceType"])
        full_urls = {entry["fullUrl"] for entry in bundle["entry"]}
        self.assertIn(bundle["entry"][0]["resource"]["subject"]["reference"], full_urls)
        resource_types = {entry["resource"]["resourceType"] for entry in bundle["entry"]}
        self.assertIn("DocumentReference", resource_types)
        self.assertIn("Observation", resource_types)
        medication = next(
            entry["resource"]
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "MedicationStatement"
        )
        self.assertEqual("unknown", medication["status"])
        self.assertNotIn("informationSource", medication)
        allergy = next(
            entry["resource"]
            for entry in bundle["entry"]
            if entry["resource"]["resourceType"] == "AllergyIntolerance"
        )
        self.assertEqual("active", allergy["clinicalStatus"]["coding"][0]["code"])
        self.assertEqual("unconfirmed", allergy["verificationStatus"]["coding"][0]["code"])

        restored_database = self.root / "restored" / "health.sqlite"
        restored = restore_backup(archive, restored_database)
        self.assertEqual({"integrity": "ok", "foreign_key_errors": 0}, restored["integrity"])
        restored_store = HealthMemoryStore(restored_database, seed_demo=False)
        record = restored_store.get_record(self.record_id, "mom")
        self.assertEqual("approved", record["status"])
        self.assertEqual("synthetic vault fixture", record["source"]["label"])

    def test_restore_refuses_to_overwrite_existing_database(self) -> None:
        archive = self.root / "family.coval"
        create_backup(self.database, archive)
        with self.assertRaisesRegex(VaultError, "already exists"):
            restore_backup(archive, self.database)

    def test_verify_rejects_tampered_payload(self) -> None:
        archive = self.root / "family.coval"
        create_backup(self.database, archive)
        tampered = self.root / "tampered.coval"
        with zipfile.ZipFile(archive, "r") as source:
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name in source.namelist():
                    payload = source.read(name)
                    if name == "exports/fhir-r4/mom.json":
                        payload += b"tampered"
                    target.writestr(name, payload)
        with self.assertRaisesRegex(VaultError, "integrity check failed"):
            verify_backup(tampered)

    def test_backup_never_replaces_database_or_wal_paths(self) -> None:
        for protected_path in (
            self.database,
            Path(f"{self.database}-wal"),
            Path(f"{self.database}-shm"),
        ):
            with self.assertRaisesRegex(VaultError, "must not replace"):
                create_backup(self.database, protected_path, overwrite=True)
        self.assertEqual(b"SQLite format 3\x00", self.database.read_bytes()[:16])

    def test_untrusted_member_id_cannot_escape_export_directory(self) -> None:
        unsafe_database = self.root / "unsafe" / "health.sqlite"
        unsafe_store = HealthMemoryStore(unsafe_database, seed_demo=False)
        unsafe_store.create_member(
            {
                "id": "../escaped",
                "name": "synthetic unsafe id",
                "relation": "test",
                "age": 30,
                "profile": "",
                "badges": [],
            }
        )
        with self.assertRaisesRegex(VaultError, "Unsafe family member id"):
            create_backup(unsafe_database, self.root / "unsafe.coval")
        self.assertFalse((self.root / "escaped.json").exists())

    def test_no_overwrite_install_preserves_racing_target(self) -> None:
        temporary = self.root / "temporary.sqlite"
        target = self.root / "racing-target.sqlite"
        temporary.write_bytes(b"restored")
        target.write_bytes(b"existing")
        with self.assertRaisesRegex(VaultError, "already exists"):
            _install_temporary(temporary, target, overwrite=False)
        self.assertEqual(b"existing", target.read_bytes())

    def test_fhir_mapping_does_not_invent_current_medication_or_timezone(self) -> None:
        self.assertEqual("unknown", _medication_status("reported"))
        self.assertEqual("unknown", _medication_status("started"))
        self.assertEqual("stopped", _medication_status("stopped"))
        self.assertIsNone(_fhir_datetime("2026-08-23T10:30:00"))
        self.assertEqual("2026-08-23T10:30:00+08:00", _fhir_datetime("2026-08-23T10:30:00+08:00"))

    def test_unknown_future_migration_is_rejected(self) -> None:
        with connect(self.database) as connection:
            connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                "VALUES (999, 'future.sql', ?, '2026-08-23T00:00:00Z')",
                ("f" * 64,),
            )
        with self.assertRaisesRegex(VaultError, "Unsupported future schema migration"):
            create_backup(self.database, self.root / "future.coval")

    def test_incomplete_migration_ledger_cannot_create_verified_backup(self) -> None:
        with connect(self.database) as connection:
            connection.execute("DELETE FROM schema_migrations WHERE version = 1")
        with self.assertRaisesRegex(VaultError, "not a complete supported prefix"):
            create_backup(self.database, self.root / "missing-migration.coval")

    def test_truncated_trailing_ledger_fails_restore_drill(self) -> None:
        with connect(self.database) as connection:
            connection.execute("DELETE FROM schema_migrations WHERE version IN (3, 4)")
        with self.assertRaisesRegex(VaultError, "complete supported prefix"):
            create_backup(self.database, self.root / "truncated-ledger.coval")

    def test_private_temporary_file_remains_exclusively_created(self) -> None:
        target = self.root / "private-output.coval"
        temporary = _temporary_sibling(target)
        try:
            self.assertTrue(temporary.is_file())
            if os.name == "posix":
                self.assertEqual(0, stat.S_IMODE(temporary.stat().st_mode) & 0o077)
        finally:
            temporary.unlink(missing_ok=True)

    def test_non_object_manifest_fails_as_vault_error(self) -> None:
        archive = self.root / "bad-manifest.coval"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", "[]")
        with self.assertRaisesRegex(VaultError, "manifest root"):
            verify_backup(archive)


if __name__ == "__main__":
    unittest.main()
