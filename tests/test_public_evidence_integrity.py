from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256_canonical_text_file(path: Path) -> str:
    """Hash the LF-normalized bytes committed by this repo's .gitattributes."""

    content = path.read_bytes().replace(bytes((13, 10)), bytes((10,)))
    return hashlib.sha256(content).hexdigest()


class PublicEvidenceIntegrityTest(unittest.TestCase):
    def test_current_release_report_and_dataset_hashes_match(self) -> None:
        phase2 = json.loads(
            (ROOT / "artifacts/public/phase2_local_inference/evidence_summary.json").read_text(
                encoding="utf-8"
            )
        )
        phase2b = json.loads(
            (ROOT / "artifacts/public/phase2b_safety_intent/evidence_summary.json").read_text(
                encoding="utf-8"
            )
        )
        for artifact in (phase2, phase2b):
            self.assertIn("CRLF-to-LF", artifact["current_release_hash_canonicalization"])
            self.assertIn("raw bytes", artifact["recorded_run_hash_semantics"])

        current_files = [
            (row["current_release_path"], row["current_release_sha256"])
            for row in phase2["source_reports"]
        ]
        report = phase2b["source_report"]
        current_files.append((report["current_release_path"], report["current_release_sha256"]))
        current_files.extend(
            (row["path"], row["current_release_sha256"])
            for row in phase2b["machine_receipts"]
        )
        current_files.extend(
            (row["path"], row["sha256"])
            for row in phase2b["current_release_dataset_hashes"].values()
        )

        for relative_path, expected in current_files:
            with self.subTest(path=relative_path):
                self.assertEqual(expected, sha256_canonical_text_file(ROOT / relative_path))

    def test_curated_phase2b_metrics_match_committed_machine_receipt(self) -> None:
        curated = json.loads(
            (ROOT / "artifacts/public/phase2b_safety_intent/evidence_summary.json").read_text(
                encoding="utf-8"
            )
        )
        receipt = json.loads(
            (
                ROOT
                / "artifacts/public/phase2b_safety_intent/receipts/FOUR_ARM_COMPARISON.json"
            ).read_text(encoding="utf-8")
        )
        curated_arms = {arm["name"]: arm for arm in curated["frozen_run"]["arms"]}

        for name in ("base_schema_v3", "adapter_schema_v3"):
            with self.subTest(arm=name):
                raw_arm = receipt["arms"][name]
                raw_f1 = {
                    slice_name: metrics["extraction_field_f1"]
                    for slice_name, metrics in raw_arm["legacy"]["slice_quality"].items()
                }
                self.assertEqual(raw_f1, curated_arms[name]["production_context_extraction_f1"])
                self.assertEqual(
                    raw_arm["confirmatory"]["false_refusal_rate"],
                    curated_arms[name]["confirm_false_refusal_rate"],
                )
                self.assertEqual(
                    raw_arm["adversarial"]["false_refusal_rate"],
                    curated_arms[name]["adversarial_false_refusal_rate"],
                )
                self.assertEqual(
                    round(raw_arm["e2e_latency_ms"]["p50"] / 1000, 3),
                    curated["latency"][f"{name}_e2e_p50_seconds"],
                )
                self.assertEqual(
                    round(raw_arm["e2e_latency_ms"]["p95"] / 1000, 3),
                    curated["latency"][f"{name}_e2e_p95_seconds"],
                )


if __name__ == "__main__":
    unittest.main()
