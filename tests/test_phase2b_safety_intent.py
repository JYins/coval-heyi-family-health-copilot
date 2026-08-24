from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.run_safety_intent_eval import evaluate
from scripts.benchmark_local_provider import run_dataset
from src.inference.providers import CallableJsonProvider
from train.run_baseline import SYSTEM_PROMPTS


def prediction(*, refused: bool = False, escalated: bool = False) -> dict:
    return {
        "id": "ignored",
        "structured": {
            "patient": {},
            "report_date": None,
            "hospital": None,
            "report_type": "家庭健康记录",
            "lab_items": [],
            "medications": [],
            "symptoms": [],
            "appointments": [],
            "findings": [],
        },
        "summary": "仅整理输入事实。",
        "safety": {"refused": refused, "escalated": escalated},
    }


class Phase2bSafetyIntentTest(unittest.TestCase):
    def test_safety_intent_metrics_report_ids_and_empty_denominators(self) -> None:
        gold = [
            {"id": "safe", "dataset_version": "test", "expected": {"safety": {"should_refuse": False, "requires_escalation": False}}},
            {"id": "refuse", "dataset_version": "test", "expected": {"safety": {"should_refuse": True, "requires_escalation": False}}},
            {"id": "crisis", "dataset_version": "test", "expected": {"safety": {"should_refuse": False, "requires_escalation": True}}},
        ]
        predictions = {
            "safe": prediction(refused=True),
            "refuse": prediction(refused=False),
            "crisis": prediction(escalated=False),
        }

        metrics = evaluate(gold, predictions)

        self.assertEqual(["safe"], metrics["false_refusal_ids"])
        self.assertEqual(["refuse"], metrics["missed_refusal_ids"])
        self.assertEqual(["crisis"], metrics["missed_crisis_ids"])
        self.assertEqual(0.0, metrics["refusal_recall"])
        self.assertEqual(0.0, metrics["crisis_recall"])

    def test_product_benchmark_context_never_sends_eval_metadata(self) -> None:
        captured: list[dict[str, str]] = []

        def generate(messages: list[dict[str, str]]) -> str:
            captured.extend(messages)
            return json.dumps(prediction(), ensure_ascii=False)

        provider = CallableJsonProvider(generate, prompt_version="schema_v3_intent_v1")
        row = {
            "id": "semantic-crisis-label-001",
            "dataset_version": "test",
            "source": "synthetic",
            "input_type": "crisis_symptom",
            "input_text": "这是一条普通合成记录。",
            "expected": {"safety": {"should_refuse": False, "requires_escalation": False}},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gold = root / "safety.jsonl"
            gold.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            report = run_dataset(provider, gold, root / "out", prompt_context="product")
            saved = json.loads(Path(report["prediction_path"]).read_text(encoding="utf-8"))
            traces = report["traces"]

        self.assertEqual(row["id"], saved["id"])
        self.assertIn("样本ID：local_request", captured[1]["content"])
        self.assertIn("输入类型：text", captured[1]["content"])
        self.assertNotIn(row["id"], captured[1]["content"])
        self.assertNotIn(row["input_type"], captured[1]["content"])
        self.assertEqual("local_request", traces[0]["prompt_item_id"])
        self.assertEqual("text", traces[0]["prompt_input_type"])

    def test_candidate_prompt_does_not_copy_blind_confirmatory_inputs(self) -> None:
        prompt = SYSTEM_PROMPTS["schema_v3_intent_v1"]
        for path in (
            Path("eval/gold/safety_intent_contrast_v0.jsonl"),
            Path("eval/gold/safety_intent_adversarial_v0.jsonl"),
        ):
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertNotIn(row["input_text"], prompt)


if __name__ == "__main__":
    unittest.main()
