from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "manage_vault.py"


class VaultCliBoundaryTest(unittest.TestCase):
    def test_backup_requires_explicit_synthetic_unencrypted_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "backup",
                    "--database",
                    str(Path(temp_dir) / "missing.sqlite"),
                    "--output",
                    str(Path(temp_dir) / "demo.coval"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("acknowledge-synthetic-only-unencrypted", result.stderr)

    def test_help_leads_with_unencrypted_synthetic_only_boundary(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("UNENCRYPTED, SYNTHETIC-ONLY", result.stdout)
        self.assertIn("Never use real family/patient data", result.stdout)


if __name__ == "__main__":
    unittest.main()
