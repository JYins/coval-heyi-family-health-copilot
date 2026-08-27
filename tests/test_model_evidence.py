from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.serve import evidence as evidence_module


class ModelEvidenceContractTest(unittest.TestCase):
    def test_clean_release_uses_committed_blocked_candidate_evidence(self) -> None:
        evidence = evidence_module.model_evidence()
        values = {item.label: item.value for item in evidence.metrics}

        self.assertEqual("historical_product_context_audit_not_clean_clone_reproducible", evidence.status)
        self.assertIn("historical candidate", evidence.adapter)
        self.assertEqual("BLOCKED", values["Deployment decision"])
        self.assertEqual("mock-rules-v2", values["Product default"])
        self.assertEqual(
            "0.6767→0.6767 / 0.6897→0.6897 / 0.6939→0.6222",
            values["Base → adapter F1"],
        )
        self.assertEqual("base 50.00% / adapter 50.00%", values["False refusal"])
        self.assertEqual("REJECTED", values["Prompt ablation"])

    def test_malformed_committed_metric_fails_closed(self) -> None:
        source = json.loads(evidence_module.PHASE2B_EVIDENCE.read_text(encoding="utf-8"))
        del source["latency"]["adapter_schema_v3_e2e_p95_seconds"]

        with TemporaryDirectory() as temp_dir:
            malformed = Path(temp_dir) / "evidence_summary.json"
            malformed.write_text(json.dumps(source), encoding="utf-8")
            with patch.object(evidence_module, "PHASE2B_EVIDENCE", malformed):
                evidence = evidence_module.model_evidence()

        self.assertEqual("evidence_unavailable", evidence.status)
        self.assertEqual("Evidence status", evidence.metrics[0].label)
        self.assertIn("KeyError", evidence.metrics[0].value)


if __name__ == "__main__":
    unittest.main()
