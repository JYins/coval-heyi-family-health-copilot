from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.inference.providers import (
    CallableJsonProvider,
    MockProvider,
    ProviderOutputError,
    build_provider_from_env,
    outbound_network_guard,
)
from src.serve.api_schemas import SafetyState, StructuringRequest
from src.serve.memory_api import create_app


def valid_prediction(*, escalated: bool = False, refused: bool = False) -> str:
    return json.dumps(
        {
            "id": "ignored",
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [{"text": "咳嗽", "onset": "昨晚"}],
                "appointments": [],
                "findings": [],
            },
            "summary": "昨晚开始咳嗽。",
            "safety": {"refused": refused, "escalated": escalated},
        },
        ensure_ascii=False,
    )


class ModelProviderTest(unittest.TestCase):
    def test_mock_provider_exposes_provenance_and_needs_no_network(self) -> None:
        provider = MockProvider()
        payload = StructuringRequest(member_id="mom", text="昨晚开始咳嗽")
        with outbound_network_guard():
            result = provider.structure(payload, item_id="mock-1")
            with self.assertRaisesRegex(OSError, "offline guard blocked"):
                socket.create_connection(("example.com", 443), timeout=0.01)
        self.assertEqual("mock", result.response.inference.provider)
        self.assertTrue(result.response.inference.offline_only)
        self.assertEqual("mock-1", result.prediction["id"])

    def test_model_contract_repairs_once_and_safety_overlay_cannot_downgrade(self) -> None:
        outputs = iter(["not json", valid_prediction(escalated=False)])
        provider = CallableJsonProvider(lambda _messages: next(outputs))
        payload = StructuringRequest(member_id="mom", text="现在胸痛，还喘不上气")
        result = provider.structure(payload, item_id="crisis-1", input_type="crisis_symptom")
        self.assertEqual(2, result.attempts)
        self.assertEqual(SafetyState.escalated, result.response.safety)
        self.assertTrue(result.prediction["safety"]["escalated"])
        self.assertEqual(0, result.response.forbidden_advice_generated)

    def test_model_contract_fails_after_bounded_retry(self) -> None:
        provider = CallableJsonProvider(lambda _messages: "still not json")
        payload = StructuringRequest(member_id="mom", text="昨晚开始咳嗽")
        with self.assertRaises(ProviderOutputError):
            provider.structure(payload)

    def test_model_contract_repairs_known_singleton_collection_shape(self) -> None:
        prediction = json.loads(valid_prediction())
        prediction["structured"]["symptoms"] = {"text": "咳嗽", "onset": "昨晚"}
        prediction["structured"]["medications"] = [None]
        prediction["structured"]["safety"] = {"refused": False, "escalated": False}
        provider = CallableJsonProvider(
            lambda _messages: json.dumps(prediction, ensure_ascii=False)
        )

        result = provider.structure(
            StructuringRequest(member_id="mom", text="昨晚开始咳嗽"),
            item_id="singleton-1",
        )

        self.assertEqual(1, result.attempts)
        self.assertEqual("咳嗽", result.prediction["structured"]["symptoms"][0]["text"])
        self.assertEqual([], result.prediction["structured"]["medications"])
        self.assertNotIn("safety", result.prediction["structured"])

    def test_missing_explicit_local_provider_never_falls_back_to_mock(self) -> None:
        with patch.dict(
            os.environ,
            {"COVAL_MODEL_PROVIDER": "transformers_adapter"},
            clear=True,
        ):
            provider = build_provider_from_env()
        self.assertEqual("transformers_adapter", provider.describe().provider)
        self.assertEqual("error", provider.describe().state)
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(Path(temp_dir) / "memory.sqlite", provider=provider))
            health = client.get("/health").json()
            self.assertEqual("transformers_adapter", health["llm_service"])
            self.assertEqual("error", health["model_runtime"]["state"])
            response = client.post(
                "/structure",
                json={"member_id": "mom", "text": "昨晚开始咳嗽"},
            )
            self.assertEqual(503, response.status_code)
            self.assertEqual("provider_unavailable", response.json()["code"])

    def test_base_benchmark_provider_is_explicit_and_never_uses_adapter(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COVAL_MODEL_PROVIDER": "transformers_base",
                "COVAL_MODEL_BASE_PATH": str(Path(tempfile.gettempdir()) / "missing-base"),
            },
            clear=True,
        ):
            provider = build_provider_from_env()

        descriptor = provider.describe()
        self.assertEqual("transformers_base", descriptor.provider)
        self.assertIsNone(descriptor.adapter_ref)
        self.assertEqual("base-schema-v3-template-v1", descriptor.extraction_version)

    def test_provider_backed_ingestion_is_offline_idempotent_and_persists_provenance(self) -> None:
        calls = 0

        def generate(_messages: list[dict[str, str]]) -> str:
            nonlocal calls
            calls += 1
            return valid_prediction()

        provider = CallableJsonProvider(generate)
        ingestion = {
            "member_id": "mom",
            "text": "昨晚开始咳嗽",
            "input_mode": "text",
            "source_label": "合成 provider 测试",
            "idempotency_key": "provider-ingest-0001",
        }
        with tempfile.TemporaryDirectory() as temp_dir, outbound_network_guard():
            database = Path(temp_dir) / "memory.sqlite"
            client = TestClient(create_app(database, provider=provider))
            first = client.post("/ingestions", json=ingestion)
            second = client.post("/ingestions", json=ingestion)
            self.assertEqual(201, first.status_code)
            self.assertEqual(201, second.status_code)
            self.assertEqual(1, calls)
            record = first.json()
            self.assertEqual("transformers_adapter", record["extraction"]["provider"])
            self.assertIn("LoRA SFT v2", record["extraction"]["model_ref"])
            self.assertEqual("sft-v2-schema-v3-template-v1", record["extraction"]["extraction_version"])

    def test_prompt_version_is_instance_scoped_and_product_context_has_no_gold_metadata(self) -> None:
        captured: list[dict[str, str]] = []

        def generate(messages: list[dict[str, str]]) -> str:
            captured.extend(messages)
            return valid_prediction()

        provider = CallableJsonProvider(generate, prompt_version="schema_v3_intent_v1")
        result = provider.structure(
            StructuringRequest(member_id="mom", text="请记录医生已经开出的药物，不要提供新建议")
        )

        self.assertEqual("schema_v3_intent_v1", provider.describe().prompt_version)
        self.assertEqual(
            "sft-v2-schema-v3-intent-v1-template-v1",
            provider.describe().extraction_version,
        )
        self.assertIn("样本ID：local_request", captured[1]["content"])
        self.assertIn("输入类型：text", captured[1]["content"])
        self.assertNotIn("medication_note", captured[1]["content"])
        self.assertNotIn("safety_request", captured[1]["content"])
        self.assertEqual("local_request", result.trace["prompt_item_id"])
        self.assertEqual("text", result.trace["prompt_input_type"])

    def test_safety_trace_separates_model_guard_and_final_decisions(self) -> None:
        model_refusal = CallableJsonProvider(lambda _messages: valid_prediction(refused=True))
        model_result = model_refusal.structure(
            StructuringRequest(member_id="mom", text="只整理药名，不提供建议")
        )
        self.assertEqual({"refused": True, "escalated": False}, model_result.trace["model_safety"])
        self.assertEqual({"refused": False, "escalated": False}, model_result.trace["guard_safety"])
        self.assertEqual("model", model_result.trace["decision_source"])

        guard_refusal = CallableJsonProvider(lambda _messages: valid_prediction())
        guard_result = guard_refusal.structure(
            StructuringRequest(member_id="mom", text="今晚能不能多吃一片降压药")
        )
        self.assertEqual({"refused": False, "escalated": False}, guard_result.trace["model_safety"])
        self.assertEqual({"refused": True, "escalated": False}, guard_result.trace["guard_safety"])
        self.assertEqual({"refused": True, "escalated": False}, guard_result.trace["final_safety"])
        self.assertEqual("deterministic_guard", guard_result.trace["decision_source"])

    def test_unknown_prompt_version_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COVAL_MODEL_PROVIDER": "transformers_adapter",
                "COVAL_MODEL_PROMPT_VERSION": "not-a-real-prompt",
            },
            clear=True,
        ):
            provider = build_provider_from_env()
        self.assertEqual("error", provider.describe().state)
        self.assertIn("unknown COVAL_MODEL_PROMPT_VERSION", provider.describe().detail)


if __name__ == "__main__":
    unittest.main()
