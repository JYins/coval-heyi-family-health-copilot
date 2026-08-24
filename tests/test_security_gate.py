from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.health_memory.security_gate import parse_real_data_mode, sqlite_wal_fix_present
from src.serve.memory_api import create_app


class SecurityGateTest(unittest.TestCase):
    def test_sqlite_wal_fix_version_rules_are_explicit(self) -> None:
        self.assertFalse(sqlite_wal_fix_present("3.50.4"))
        self.assertTrue(sqlite_wal_fix_present("3.50.7"))
        self.assertFalse(sqlite_wal_fix_present("3.51.2"))
        self.assertTrue(sqlite_wal_fix_present("3.51.3"))
        self.assertTrue(sqlite_wal_fix_present("3.52.0"))

    def test_real_data_mode_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"COVAL_REAL_DATA_MODE": "1"}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "Real-data mode is fail-closed"):
                create_app(Path(temp_dir) / "memory.sqlite")

    def test_invalid_real_data_mode_does_not_silently_enable_writer(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "COVAL_REAL_DATA_MODE must be"):
            parse_real_data_mode("enabled")

    def test_health_exposes_synthetic_only_gate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"COVAL_REAL_DATA_MODE": "false"}, clear=False
        ):
            health = TestClient(create_app(Path(temp_dir) / "memory.sqlite")).get("/health")
        self.assertEqual(200, health.status_code)
        gate = health.json()["real_data_gate"]
        self.assertTrue(gate["gate_enforced"])
        self.assertFalse(gate["real_data_enabled"])
        self.assertFalse(gate["ready"])
        self.assertEqual("synthetic_public_only", gate["mode"])
        self.assertGreaterEqual(len(gate["blockers"]), 5)


if __name__ == "__main__":
    unittest.main()
