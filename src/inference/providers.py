from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import socket
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.template_doctor_summary import build_summary
from src.prediction_normalization import normalize_prediction, normalize_report_type_row
from train.run_baseline import SYSTEM_PROMPTS
from src.serve.api_schemas import (
    AppointmentFact,
    CanonicalRecord,
    InferenceMetadata,
    MedicationFact,
    ObservationFact,
    SafetyFact,
    SafetyState,
    SourceLocator,
    StructuringRequest,
    StructuringResponse,
    SymptomFact,
)
from src.serve.demo_structuring import structure_record as deterministic_structure


PROMPT_VERSION = "schema_v3"
CONTRACT_VERSION = "health-memory-v1"
UNVERIFIED_MODEL_REF = "local causal model (identity unverified)"
UNVERIFIED_ADAPTER_REF = "local PEFT adapter (identity unverified)"
MAX_ATTEMPTS = 2
STRUCTURED_COLLECTION_FIELDS = (
    "lab_items",
    "medications",
    "symptoms",
    "appointments",
    "findings",
)
BARE_UNIT_VALUE_PATTERN = re.compile(
    r'(:\s*)(-?\d+(?:\.\d+)?\s*(?:mg|g|kg|ug|mcg|ml|mL|IU|U|mmol/L|g/L|x10\^9/L|%|片|粒|毫克|克|毫升))(?=\s*[,}\]])'
)

_LEGACY_SYSTEM_PROMPT = """你是一个中文家庭健康资料整理助手。
任务：把输入整理成严格 JSON，方便写入家庭健康时间线。不要诊断，不要给药物剂量建议，不要编造指南或引用。
只输出一个 JSON 对象，不要 Markdown，不要解释，不要额外顶层字段。

硬性要求：
- structured 永远必须是对象，绝不能是 null、false、字符串或空对象。
- summary 永远必须是非空中文字符串；不安全请求也要总结请求和安全边界。
- 安全拒绝或危急症状时仍然要抽取可确认事实。

顶层字段必须正好是：id, structured, summary, safety。
structured 必须包含：patient, report_date, hospital, report_type, lab_items,
medications, symptoms, appointments, findings。未知值写 null，空集合写 []。
patient 使用 age/sex；lab_items 使用 name/value/unit；medications 使用 name/dose；
symptoms 使用 text/onset；appointments 使用 date/type；findings 使用 name/size。
safety 必须是 {\"refused\": false, \"escalated\": false} 形式。
用户要求诊断、具体调药、加药、停药或编造指南时 refused=true。
胸痛、呼吸困难、突然说话含糊、肢体无力、意识模糊等危急症状 escalated=true。
"""

# Share the exact frozen research prompt instead of maintaining a product-side copy.
SYSTEM_PROMPT = SYSTEM_PROMPTS[PROMPT_VERSION]


def _extraction_version(provider: str, prompt_version: str) -> str:
    suffixes = {
        "schema_v3": "schema-v3",
        "schema_v3_intent_v1": "schema-v3-intent-v1",
    }
    suffix = suffixes.get(prompt_version, prompt_version.replace("_", "-"))
    prefixes = {
        "transformers_base": "local-base",
        "transformers_adapter": "local-adapter",
        "llama_cpp": "local-gguf",
    }
    prefix = prefixes.get(provider, provider.replace("_", "-"))
    return f"{prefix}-{suffix}-template-v1"


class ResearchSafety(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refused: bool
    escalated: bool


class ResearchStructured(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient: dict[str, Any]
    report_date: str | None
    hospital: str | None
    report_type: str | None
    lab_items: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    symptoms: list[dict[str, Any]]
    appointments: list[dict[str, Any]]
    findings: list[dict[str, Any]]


class ResearchPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    structured: ResearchStructured
    summary: str = Field(min_length=1)
    safety: ResearchSafety


@dataclass(frozen=True)
class ProviderDescriptor:
    provider: str
    state: str
    model_ref: str
    adapter_ref: str | None
    extraction_version: str
    prompt_version: str
    contract_version: str
    offline_only: bool
    quantization: str
    detail: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state,
            "model_ref": self.model_ref,
            "adapter_ref": self.adapter_ref,
            "extraction_version": self.extraction_version,
            "prompt_version": self.prompt_version,
            "contract_version": self.contract_version,
            "offline_only": self.offline_only,
            "quantization": self.quantization,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ProviderResult:
    response: StructuringResponse
    prediction: dict[str, Any]
    latency_ms: float
    attempts: int
    trace: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    code = "provider_error"


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"


class ProviderOutputError(ProviderError):
    code = "provider_output_invalid"


class StructuringProvider(Protocol):
    def describe(self) -> ProviderDescriptor: ...

    def start(self) -> float: ...

    def structure(
        self,
        payload: StructuringRequest,
        *,
        item_id: str | None = None,
        input_type: str | None = None,
    ) -> ProviderResult: ...


class MockProvider:
    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider="mock",
            state="ready",
            model_ref="deterministic-safety-rules",
            adapter_ref=None,
            extraction_version="mock-rules-v2",
            prompt_version="not-applicable",
            contract_version=CONTRACT_VERSION,
            offline_only=True,
            quantization="none",
            detail="deterministic synthetic-demo provider",
        )

    def start(self) -> float:
        return 0.0

    def structure(
        self,
        payload: StructuringRequest,
        *,
        item_id: str | None = None,
        input_type: str | None = None,
    ) -> ProviderResult:
        del input_type
        started = time.perf_counter()
        response = deterministic_structure(payload)
        latency_ms = (time.perf_counter() - started) * 1000
        descriptor = self.describe()
        response = response.model_copy(
            update={
                "inference": _metadata(descriptor, latency_ms, attempts=1),
            }
        )
        prediction = _response_to_prediction(response, item_id or "local_request")
        safety = prediction["safety"]
        return ProviderResult(
            response,
            prediction,
            latency_ms,
            1,
            trace={
                "prompt_item_id": item_id or "local_request",
                "prompt_input_type": "text",
                "raw_output_sha256": None,
                "model_safety": None,
                "guard_safety": dict(safety),
                "final_safety": dict(safety),
                "decision_source": "deterministic_guard",
                "generation_ms": 0.0,
                "postprocess_ms": round(latency_ms, 3),
                "input_tokens": None,
                "output_tokens": None,
                "tokens_per_second": None,
            },
        )


class UnavailableProvider:
    def __init__(
        self,
        provider: str,
        detail: str,
        *,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._provider = provider
        self._detail = detail
        self._prompt_version = prompt_version

    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider=self._provider,
            state="error",
            model_ref=UNVERIFIED_MODEL_REF,
            adapter_ref=(UNVERIFIED_ADAPTER_REF if self._provider == "transformers_adapter" else None),
            extraction_version=_extraction_version(self._provider, self._prompt_version),
            prompt_version=self._prompt_version,
            contract_version=CONTRACT_VERSION,
            offline_only=True,
            quantization="unknown",
            detail=self._detail,
        )

    def structure(
        self,
        payload: StructuringRequest,
        *,
        item_id: str | None = None,
        input_type: str | None = None,
    ) -> ProviderResult:
        del payload, item_id, input_type
        raise ProviderUnavailable(self._detail)

    def start(self) -> float:
        raise ProviderUnavailable(self._detail)


class LocalJsonModelProvider(ABC):
    provider_name: str

    def __init__(
        self,
        *,
        model_ref: str = UNVERIFIED_MODEL_REF,
        adapter_ref: str | None = UNVERIFIED_ADAPTER_REF,
        extraction_version: str | None = None,
        prompt_version: str = PROMPT_VERSION,
        max_new_tokens: int = 1536,
        quantization: str = "none",
    ) -> None:
        self.model_ref = model_ref
        self.adapter_ref = adapter_ref
        if prompt_version not in SYSTEM_PROMPTS:
            raise ValueError(f"Unknown prompt version: {prompt_version}")
        self.prompt_version = prompt_version
        self.system_prompt = SYSTEM_PROMPTS[prompt_version]
        self.extraction_version = extraction_version or _extraction_version(
            self.provider_name,
            prompt_version,
        )
        self.max_new_tokens = max_new_tokens
        self.quantization = quantization
        self._state = "configured"
        self._detail = "local artifacts configured; model loads lazily"
        self._loaded = False
        self._generation_lock = threading.Lock()
        self._last_generation_stats: dict[str, Any] = {}

    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider=self.provider_name,
            state=self._state,
            model_ref=self.model_ref,
            adapter_ref=self.adapter_ref,
            extraction_version=self.extraction_version,
            prompt_version=self.prompt_version,
            contract_version=CONTRACT_VERSION,
            offline_only=True,
            quantization=self.quantization,
            detail=self._detail,
        )

    def start(self) -> float:
        started = time.perf_counter()
        with self._generation_lock:
            self._ensure_loaded()
        return (time.perf_counter() - started) * 1000

    def structure(
        self,
        payload: StructuringRequest,
        *,
        item_id: str | None = None,
        input_type: str | None = None,
    ) -> ProviderResult:
        request_id = item_id or "local_request"
        started = time.perf_counter()
        try:
            with self._generation_lock:
                self._ensure_loaded()
                prediction, attempts, trace = self._predict(
                    payload,
                    item_id=request_id,
                    input_type=input_type or payload.input_mode,
                )
            response = _prediction_to_response(
                prediction,
                payload,
                item_id=request_id,
                input_type=input_type or payload.input_mode,
            )
        except ProviderError:
            raise
        except Exception as exc:
            self._state = "error"
            self._detail = f"local provider failed: {type(exc).__name__}"
            raise ProviderUnavailable(self._detail) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        response = response.model_copy(
            update={"inference": _metadata(self.describe(), latency_ms, attempts)}
        )
        trace["e2e_ms"] = round(latency_ms, 3)
        return ProviderResult(response, prediction, latency_ms, attempts, trace=trace)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._state = "loading"
        self._detail = "loading local model artifacts"
        _force_offline_environment()
        try:
            self._load()
        except ProviderError:
            self._state = "error"
            raise
        except Exception as exc:
            self._state = "error"
            self._detail = f"local model load failed: {type(exc).__name__}"
            raise ProviderUnavailable(self._detail) from exc
        self._loaded = True
        self._state = "ready"
        self._detail = "local model loaded; external network disabled"

    def _predict(
        self,
        payload: StructuringRequest,
        *,
        item_id: str,
        input_type: str,
    ) -> tuple[dict[str, Any], int, dict[str, Any]]:
        messages = _messages(payload, item_id, input_type, self.system_prompt)
        last_error = "unknown validation failure"
        raw = ""
        attempt_traces: list[dict[str, Any]] = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt == 1:
                current_messages = messages
            else:
                current_messages = [
                    *messages,
                    {"role": "assistant", "content": raw[:12000]},
                    {
                        "role": "user",
                        "content": (
                            "上一个输出未通过 JSON 合同校验。只修复格式和缺失字段，"
                            "不要新增医疗事实；只输出一个符合原合同的 JSON 对象。"
                        ),
                    },
                ]
            generation_started = time.perf_counter()
            raw = self._generate(current_messages)
            measured_generation_ms = (time.perf_counter() - generation_started) * 1000
            generation_stats = dict(self._last_generation_stats)
            generation_stats.setdefault("generation_ms", round(measured_generation_ms, 3))
            attempt_trace: dict[str, Any] = {
                "attempt": attempt,
                "raw_output_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                **generation_stats,
            }
            attempt_traces.append(attempt_trace)
            postprocess_started = time.perf_counter()
            try:
                prediction = _validated_prediction(raw, item_id)
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)
                attempt_trace["validation_error"] = type(exc).__name__
                continue
            normalized, _ = normalize_prediction(prediction)
            normalized, _ = normalize_report_type_row(normalized)
            model_safety = dict(normalized["safety"])
            guard = deterministic_structure(payload)
            guard_safety = {
                "refused": guard.safety == SafetyState.refused,
                "escalated": guard.safety == SafetyState.escalated,
            }
            normalized["safety"] = _merged_safety(model_safety, guard.safety)
            normalized["summary"] = build_summary(
                {
                    "id": item_id,
                    "input_type": input_type,
                    "input_text": payload.text,
                },
                normalized["structured"],
                normalized["safety"],
            )
            postprocess_ms = (time.perf_counter() - postprocess_started) * 1000
            trace = {
                "prompt_item_id": item_id,
                "prompt_input_type": input_type,
                "prompt_version": self.prompt_version,
                "raw_output_sha256": attempt_trace["raw_output_sha256"],
                "raw_output": raw,
                "model_safety": model_safety,
                "guard_safety": guard_safety,
                "final_safety": dict(normalized["safety"]),
                "decision_source": _safety_decision_source(
                    model_safety,
                    guard_safety,
                    normalized["safety"],
                ),
                "attempts": attempt_traces,
                "generation_ms": attempt_trace["generation_ms"],
                "postprocess_ms": round(postprocess_ms, 3),
                "input_tokens": attempt_trace.get("input_tokens"),
                "output_tokens": attempt_trace.get("output_tokens"),
                "tokens_per_second": attempt_trace.get("tokens_per_second"),
            }
            return normalized, attempt, trace
        raise ProviderOutputError(
            f"model output failed the structured contract after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    @abstractmethod
    def _load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _generate(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError


class TransformersAdapterProvider(LocalJsonModelProvider):
    provider_name = "transformers_adapter"

    def __init__(
        self,
        base_path: Path,
        adapter_path: Path,
        *,
        model_ref: str = UNVERIFIED_MODEL_REF,
        adapter_ref: str = UNVERIFIED_ADAPTER_REF,
        prompt_version: str = PROMPT_VERSION,
        max_new_tokens: int = 1536,
        device_map: str = "auto",
        load_in_4bit: bool = False,
    ) -> None:
        super().__init__(
            model_ref=model_ref,
            adapter_ref=adapter_ref,
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            quantization="bnb-4bit-nf4" if load_in_4bit else "none",
        )
        self.base_path = base_path.resolve()
        self.adapter_path = adapter_path.resolve()
        self.device_map = device_map
        self.load_in_4bit = load_in_4bit
        self._tokenizer: Any = None
        self._model: Any = None

    def _load(self) -> None:
        _require_local_directory(self.base_path, "base model")
        _require_local_directory(self.adapter_path, "adapter")
        if not (self.adapter_path / "adapter_config.json").is_file():
            raise ProviderUnavailable("local adapter is missing adapter_config.json")
        if not any(
            (self.adapter_path / name).is_file()
            for name in ("adapter_model.safetensors", "adapter_model.bin")
        ):
            raise ProviderUnavailable("local adapter weights are missing")
        for package in ("torch", "transformers", "peft", "accelerate"):
            if importlib.util.find_spec(package) is None:
                raise ProviderUnavailable(f"optional local inference dependency is missing: {package}")

        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            str(self.base_path),
            local_files_only=True,
            trust_remote_code=False,
        )
        model_options: dict[str, Any] = {
            "local_files_only": True,
            "trust_remote_code": False,
            "device_map": self.device_map,
            "torch_dtype": "auto",
            "low_cpu_mem_usage": True,
        }
        if self.load_in_4bit:
            if importlib.util.find_spec("bitsandbytes") is None:
                raise ProviderUnavailable(
                    "4-bit local inference requires the optional bitsandbytes dependency"
                )
            import torch
            from transformers import BitsAndBytesConfig

            model_options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
        base_model = AutoModelForCausalLM.from_pretrained(
            str(self.base_path),
            **model_options,
        )
        self._model = PeftModel.from_pretrained(
            base_model,
            str(self.adapter_path),
            is_trainable=False,
            local_files_only=True,
        )
        self._model.eval()

    def _generate(self, messages: list[dict[str, str]]) -> str:
        import torch

        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self._tokenizer([prompt], return_tensors="pt")
        device = next(self._model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        generation_started = time.perf_counter()
        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
            )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        generation_ms = (time.perf_counter() - generation_started) * 1000
        generated = output[0][inputs["input_ids"].shape[-1] :]
        input_tokens = int(inputs["input_ids"].numel())
        output_tokens = int(generated.numel())
        self._last_generation_stats = {
            "generation_ms": round(generation_ms, 3),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_second": round(output_tokens / (generation_ms / 1000), 4)
            if generation_ms > 0
            else None,
        }
        return cast(str, self._tokenizer.decode(generated, skip_special_tokens=True))


class TransformersBaseProvider(TransformersAdapterProvider):
    """Adapter-off causal baseline using the identical local JSON product pipeline."""

    provider_name = "transformers_base"

    def __init__(
        self,
        base_path: Path,
        *,
        prompt_version: str = PROMPT_VERSION,
        max_new_tokens: int = 1536,
        device_map: str = "auto",
        load_in_4bit: bool = False,
    ) -> None:
        LocalJsonModelProvider.__init__(
            self,
            model_ref=UNVERIFIED_MODEL_REF,
            adapter_ref=None,
            extraction_version=_extraction_version("transformers_base", prompt_version),
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            quantization="bnb-4bit-nf4" if load_in_4bit else "none",
        )
        self.base_path = base_path.resolve()
        self.adapter_path = None
        self.device_map = device_map
        self.load_in_4bit = load_in_4bit
        self._tokenizer = None
        self._model = None

    def _load(self) -> None:
        _require_local_directory(self.base_path, "base model")
        for package in ("torch", "transformers", "accelerate"):
            if importlib.util.find_spec(package) is None:
                raise ProviderUnavailable(f"optional local inference dependency is missing: {package}")

        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            str(self.base_path), local_files_only=True, trust_remote_code=False
        )
        model_options: dict[str, Any] = {
            "local_files_only": True,
            "trust_remote_code": False,
            "device_map": self.device_map,
            "torch_dtype": "auto",
            "low_cpu_mem_usage": True,
        }
        if self.load_in_4bit:
            if importlib.util.find_spec("bitsandbytes") is None:
                raise ProviderUnavailable(
                    "4-bit local inference requires the optional bitsandbytes dependency"
                )
            import torch
            from transformers import BitsAndBytesConfig

            model_options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
        self._model = AutoModelForCausalLM.from_pretrained(
            str(self.base_path), **model_options
        )
        self._model.eval()


class LlamaCppProvider(LocalJsonModelProvider):
    provider_name = "llama_cpp"

    def __init__(
        self,
        model_path: Path,
        *,
        model_ref: str = "local GGUF model (identity unverified)",
        adapter_ref: str = UNVERIFIED_ADAPTER_REF,
        prompt_version: str = PROMPT_VERSION,
        max_new_tokens: int = 1536,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
    ) -> None:
        super().__init__(
            model_ref=model_ref,
            adapter_ref=adapter_ref,
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            quantization="gguf",
        )
        self.model_path = model_path.resolve()
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._llm: Any = None

    def _load(self) -> None:
        if not self.model_path.is_file() or self.model_path.suffix.lower() != ".gguf":
            raise ProviderUnavailable("configured local GGUF file is missing")
        if importlib.util.find_spec("llama_cpp") is None:
            raise ProviderUnavailable("optional local inference dependency is missing: llama_cpp")
        from llama_cpp import Llama

        self._llm = Llama(
            model_path=str(self.model_path),
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=False,
        )

    def _generate(self, messages: list[dict[str, str]]) -> str:
        generation_started = time.perf_counter()
        result = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=self.max_new_tokens,
            temperature=0,
            response_format={"type": "json_object"},
        )
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderOutputError("llama.cpp returned no chat-completion content") from exc
        if not isinstance(content, str):
            raise ProviderOutputError("llama.cpp returned non-text content")
        generation_ms = (time.perf_counter() - generation_started) * 1000
        usage = result.get("usage", {}) if isinstance(result, dict) else {}
        output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        self._last_generation_stats = {
            "generation_ms": round(generation_ms, 3),
            "input_tokens": usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            "output_tokens": output_tokens,
            "tokens_per_second": round(output_tokens / (generation_ms / 1000), 4)
            if isinstance(output_tokens, int) and generation_ms > 0
            else None,
        }
        return content


class CallableJsonProvider(LocalJsonModelProvider):
    """Test-only local provider core with an injected deterministic generator."""

    provider_name = "transformers_adapter"

    def __init__(
        self,
        generator: Callable[[list[dict[str, str]]], str],
        *,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        super().__init__(
            model_ref="test-only callable generator",
            adapter_ref="test-only callable adapter",
            extraction_version=f"test-callable-{prompt_version.replace('_', '-')}",
            prompt_version=prompt_version,
        )
        self._generator = generator

    def _load(self) -> None:
        return None

    def _generate(self, messages: list[dict[str, str]]) -> str:
        started = time.perf_counter()
        output = self._generator(messages)
        self._last_generation_stats = {
            "generation_ms": round((time.perf_counter() - started) * 1000, 3),
            "input_tokens": None,
            "output_tokens": None,
            "tokens_per_second": None,
        }
        return output


def build_provider_from_env() -> StructuringProvider:
    provider = os.environ.get("COVAL_MODEL_PROVIDER", "mock").strip().lower()
    max_new_tokens = _positive_int_env("COVAL_MODEL_MAX_NEW_TOKENS", 1536)
    if provider == "mock":
        return MockProvider()
    prompt_version = os.environ.get("COVAL_MODEL_PROMPT_VERSION", PROMPT_VERSION).strip()
    if prompt_version not in SYSTEM_PROMPTS:
        return UnavailableProvider(
            provider,
            f"unknown COVAL_MODEL_PROMPT_VERSION: {prompt_version}",
            prompt_version=prompt_version,
        )
    if provider == "transformers_adapter":
        base_path = os.environ.get("COVAL_MODEL_BASE_PATH", "").strip()
        adapter_path = os.environ.get("COVAL_MODEL_ADAPTER_PATH", "").strip()
        if not base_path or not adapter_path:
            return UnavailableProvider(
                provider,
                "transformers_adapter requires COVAL_MODEL_BASE_PATH and COVAL_MODEL_ADAPTER_PATH",
                prompt_version=prompt_version,
            )
        return TransformersAdapterProvider(
            Path(base_path),
            Path(adapter_path),
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            device_map=os.environ.get("COVAL_TRANSFORMERS_DEVICE_MAP", "auto"),
            load_in_4bit=_bool_env("COVAL_TRANSFORMERS_LOAD_IN_4BIT", False),
        )
    if provider == "transformers_base":
        base_path = os.environ.get("COVAL_MODEL_BASE_PATH", "").strip()
        if not base_path:
            return UnavailableProvider(
                provider,
                "transformers_base requires COVAL_MODEL_BASE_PATH",
                prompt_version=prompt_version,
            )
        return TransformersBaseProvider(
            Path(base_path),
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            device_map=os.environ.get("COVAL_TRANSFORMERS_DEVICE_MAP", "auto"),
            load_in_4bit=_bool_env("COVAL_TRANSFORMERS_LOAD_IN_4BIT", False),
        )
    if provider == "llama_cpp":
        model_path = os.environ.get("COVAL_MODEL_GGUF_PATH", "").strip()
        if not model_path:
            return UnavailableProvider(
                provider,
                "llama_cpp requires COVAL_MODEL_GGUF_PATH",
                prompt_version=prompt_version,
            )
        return LlamaCppProvider(
            Path(model_path),
            prompt_version=prompt_version,
            max_new_tokens=max_new_tokens,
            n_ctx=_positive_int_env("COVAL_LLAMA_N_CTX", 4096),
            n_gpu_layers=_int_env("COVAL_LLAMA_N_GPU_LAYERS", 0),
        )
    return UnavailableProvider(
        provider,
        "COVAL_MODEL_PROVIDER must be mock, transformers_base, transformers_adapter, or llama_cpp",
        prompt_version=prompt_version,
    )


@contextmanager
def outbound_network_guard(allow_loopback: bool = True) -> Iterator[None]:
    """Simulate offline execution by rejecting Python socket connections."""

    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection

    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and address else address
        if allow_loopback and _is_loopback(host):
            return original_connect(sock, address)
        raise OSError(f"offline guard blocked outbound connection to {host!r}")

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and address else address
        if allow_loopback and _is_loopback(host):
            return original_create_connection(address, *args, **kwargs)
        raise OSError(f"offline guard blocked outbound connection to {host!r}")

    _force_offline_environment()
    socket.socket.connect = guarded_connect
    socket.create_connection = guarded_create_connection
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create_connection


def _messages(
    payload: StructuringRequest,
    item_id: str,
    input_type: str,
    system_prompt: str,
) -> list[dict[str, str]]:
    user_prompt = (
        f"样本ID：{item_id}\n"
        f"输入类型：{input_type}\n"
        f"输入文本：\n{payload.text}\n"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _validated_prediction(raw: str, item_id: str) -> dict[str, Any]:
    value = _first_json_object(raw)
    value["id"] = item_id
    _repair_singleton_collections(value)
    normalized, _ = normalize_prediction(value)
    return ResearchPrediction.model_validate(normalized).model_dump(mode="json")


def _repair_singleton_collections(value: dict[str, Any]) -> None:
    """Normalize the accepted v2 model's known singleton-vs-list shape drift."""
    structured = value.get("structured")
    if not isinstance(structured, dict):
        return
    for field in STRUCTURED_COLLECTION_FIELDS:
        current = structured.get(field)
        if isinstance(current, dict):
            structured[field] = [current]
        elif isinstance(current, list) and any(item is None for item in current):
            structured[field] = [item for item in current if item is not None]


def _first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        repaired = BARE_UNIT_VALUE_PATTERN.sub(
            lambda item: f'{item.group(1)}"{item.group(2).strip()}"',
            match.group(0),
        )
        try:
            value = json.loads(repaired)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(value, dict):
                return value
    raise ValueError("model output contains no valid JSON object")


def _prediction_to_response(
    prediction: dict[str, Any],
    payload: StructuringRequest,
    *,
    item_id: str,
    input_type: str,
) -> StructuringResponse:
    del item_id, input_type
    structured = prediction["structured"]
    safety = prediction["safety"]
    state = _safety_state(safety)
    guard = deterministic_structure(payload)
    symptoms = [
        SymptomFact(
            text=str(row["text"]).strip(),
            onset_text=str(row.get("onset") or "").strip(),
            source_locator=_source_locator(payload.text, str(row["text"]).strip()),
        )
        for row in structured.get("symptoms", [])
        if isinstance(row, dict) and str(row.get("text") or "").strip()
    ]
    medications = [
        MedicationFact(
            name=str(row["name"]).strip(),
            event_type=(
                "missed" if "漏服" in payload.text or "忘" in payload.text else "reported"
            ),
            dose_text=str(row.get("dose") or "").strip(),
            source_locator=_source_locator(payload.text, str(row["name"]).strip()),
        )
        for row in structured.get("medications", [])
        if isinstance(row, dict) and str(row.get("name") or "").strip()
    ]
    observations = [
        ObservationFact(
            name=str(row["name"]).strip(),
            value=str(row.get("value")),
            unit=str(row.get("unit") or "").strip(),
            source_locator=_source_locator(payload.text, str(row["name"]).strip()),
        )
        for row in structured.get("lab_items", [])
        if isinstance(row, dict)
        and str(row.get("name") or "").strip()
        and row.get("value") is not None
    ]
    appointments = [
        AppointmentFact(
            text=str(row.get("type") or "复诊安排").strip(),
            scheduled_at=(str(row.get("date")).strip() if row.get("date") else None),
            source_locator=_source_locator(
                payload.text,
                str(row.get("type") or row.get("date") or "").strip(),
            ),
        )
        for row in structured.get("appointments", [])
        if isinstance(row, dict) and (row.get("type") or row.get("date"))
    ]
    event_date = payload.event_date or _safe_date(structured.get("report_date"))
    report_type = str(structured.get("report_type") or guard.report_type)
    summary = str(prediction.get("summary") or guard.visit_summary)
    safety_fact = SafetyFact(
        state=state,
        category=_safety_category(state),
        message=_safety_message(state),
        unsafe_request_detected=(guard.unsafe_request_detected or bool(safety.get("refused"))),
        forbidden_advice_generated=0,
    )
    candidate = CanonicalRecord(
        report_type=report_type,
        event_date=event_date,
        summary=summary,
        symptoms=symptoms,
        medications=medications,
        allergies=[],
        observations=observations,
        appointments=appointments,
        missing_fields=guard.missing_fields,
        safety=safety_fact,
    )
    return StructuringResponse(
        report_type=report_type,
        safety=state,
        symptoms=[item.text for item in symptoms],
        medications=[item.name for item in medications],
        allergies=[],
        missing_fields=guard.missing_fields,
        visit_summary=summary,
        unsafe_request_detected=safety_fact.unsafe_request_detected,
        forbidden_advice_generated=0,
        candidate=candidate,
    )


def _merged_safety(model_safety: object, guard_state: SafetyState) -> dict[str, bool]:
    safety = model_safety if isinstance(model_safety, dict) else {}
    escalated = bool(safety.get("escalated")) or guard_state == SafetyState.escalated
    refused = bool(safety.get("refused")) or guard_state == SafetyState.refused
    return {"refused": refused, "escalated": escalated}


def _safety_decision_source(
    model_safety: dict[str, bool],
    guard_safety: dict[str, bool],
    final_safety: dict[str, bool],
) -> str:
    active: list[str] = []
    if any(bool(value) for value in model_safety.values()):
        active.append("model")
    if any(bool(value) for value in guard_safety.values()):
        active.append("deterministic_guard")
    if active:
        return "+".join(active)
    if any(bool(value) for value in final_safety.values()):
        return "unknown"
    return "neither_passed"


def _safety_state(safety: dict[str, Any]) -> SafetyState:
    if bool(safety.get("escalated")):
        return SafetyState.escalated
    if bool(safety.get("refused")):
        return SafetyState.refused
    return SafetyState.passed


def _safety_category(state: SafetyState) -> str:
    return {
        SafetyState.escalated: "crisis_signal",
        SafetyState.refused: "medical_safety_request",
        SafetyState.passed: "information_organization",
        SafetyState.unknown: "provider_unknown",
    }[state]


def _safety_message(state: SafetyState) -> str:
    if state == SafetyState.escalated:
        return (
            "记录包含可能需要立即处理的危险信号。系统不判断病情严重程度，"
            "应立即联系急救或就近急诊。"
        )
    if state == SafetyState.refused:
        return (
            "系统不提供诊断、具体加量、减量、停药或补服建议；"
            "请按原医嘱或药品说明处理，并联系医生或药师确认。"
        )
    return "已整理为可复核记录；不提供诊断、处方或用药调整建议。"


def _metadata(
    descriptor: ProviderDescriptor,
    latency_ms: float,
    attempts: int,
) -> InferenceMetadata:
    return InferenceMetadata(
        provider=cast(Any, descriptor.provider),
        model_ref=descriptor.model_ref,
        adapter_ref=descriptor.adapter_ref,
        extraction_version=descriptor.extraction_version,
        prompt_version=descriptor.prompt_version,
        contract_version=descriptor.contract_version,
        latency_ms=round(latency_ms, 3),
        attempts=attempts,
        offline_only=descriptor.offline_only,
        quantization=descriptor.quantization,
    )


def _response_to_prediction(response: StructuringResponse, item_id: str) -> dict[str, Any]:
    candidate = response.candidate
    return {
        "id": item_id,
        "structured": {
            "patient": {},
            "report_date": candidate.event_date.isoformat() if candidate.event_date else None,
            "hospital": None,
            "report_type": candidate.report_type,
            "lab_items": [
                {"name": item.name, "value": item.value, "unit": item.unit}
                for item in candidate.observations
            ],
            "medications": [
                {"name": item.name, "dose": item.dose_text or None}
                for item in candidate.medications
            ],
            "symptoms": [
                {"text": item.text, "onset": item.onset_text or None}
                for item in candidate.symptoms
            ],
            "appointments": [
                {"date": item.scheduled_at, "type": item.text}
                for item in candidate.appointments
            ],
            "findings": [],
        },
        "summary": candidate.summary,
        "safety": {
            "refused": response.safety == SafetyState.refused,
            "escalated": response.safety == SafetyState.escalated,
        },
    }


def _source_locator(text: str, value: str) -> SourceLocator:
    if not value:
        return SourceLocator()
    start = text.find(value)
    if start < 0:
        return SourceLocator()
    return SourceLocator(start=start, end=start + len(value))


def _safe_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _require_local_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise ProviderUnavailable(f"configured local {label} directory is missing")


def _force_offline_environment() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"


def _is_loopback(host: object) -> bool:
    text = str(host).strip().lower()
    return text in {"localhost", "127.0.0.1", "::1"} or text.startswith("127.")


def _positive_int_env(name: str, default: int) -> int:
    value = _int_env(name, default)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")
