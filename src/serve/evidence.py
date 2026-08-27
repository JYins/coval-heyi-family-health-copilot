from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .api_schemas import ModelEvidenceItem, ModelEvidenceResponse


ROOT = Path(__file__).resolve().parents[2]
PHASE2_EVIDENCE = ROOT / "artifacts" / "public" / "phase2_local_inference" / "evidence_summary.json"
PHASE2B_EVIDENCE = ROOT / "artifacts" / "public" / "phase2b_safety_intent" / "evidence_summary.json"
SFT_V2_MANIFEST = "data/public/sft_v2/manifest.json"


def model_evidence() -> ModelEvidenceResponse:
    """Return only committed, public-safe model evidence.

    Ignored local ``results/`` directories must never change public claims. The
    curated summaries describe a historical audit and its blocked deployment.
    """

    try:
        phase2 = _load_object(PHASE2_EVIDENCE)
        phase2b = _load_object(PHASE2B_EVIDENCE)
        identity = _object(phase2, "identity")
        frozen_run = _object(phase2b, "frozen_run")
        base_arm = _arm(frozen_run, "base_schema_v3")
        adapter_arm = _arm(frozen_run, "adapter_schema_v3")
        base_quality = _object(base_arm, "production_context_extraction_f1")
        adapter_quality = _object(adapter_arm, "production_context_extraction_f1")
        latency = _object(phase2b, "latency")
        prompt_decision = _object(phase2b, "decision")
        source = _relative(PHASE2_EVIDENCE)
        slice_names = ("synthetic_v0", "medication_contrast_v0", "safety_onset_edge_v1_1")
        extraction = " / ".join(
            f"{_decimal(base_quality[name])}→{_decimal(adapter_quality[name])}"
            for name in slice_names
        )
        false_refusal = (
            f"base {_percent(base_arm['confirm_false_refusal_rate'])} / "
            f"adapter {_percent(adapter_arm['confirm_false_refusal_rate'])}"
        )
        warm_latency = (
            f"{_decimal(latency['adapter_schema_v3_e2e_p50_seconds'], 3)}s / "
            f"{_decimal(latency['adapter_schema_v3_e2e_p95_seconds'], 3)}s"
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return ModelEvidenceResponse(
            base_model="Qwen/Qwen2.5-7B-Instruct",
            adapter="No verified research candidate",
            status="evidence_unavailable",
            metrics=[
                ModelEvidenceItem(
                    label="Evidence status",
                    value=f"unavailable ({type(exc).__name__})",
                    source="artifacts/public",
                )
            ],
        )

    return ModelEvidenceResponse(
        base_model=str(identity.get("base_model", "Qwen/Qwen2.5-7B-Instruct")),
        adapter="LoRA SFT v2 NF4 (historical candidate)",
        status="historical_product_context_audit_not_clean_clone_reproducible",
        metrics=[
            ModelEvidenceItem(
                label="Deployment decision",
                value=str(prompt_decision.get("adapter_deployment", "UNKNOWN")),
                source=_relative(PHASE2B_EVIDENCE),
            ),
            ModelEvidenceItem(
                label="Product default",
                value=str(prompt_decision.get("product_default", "unknown")),
                source=_relative(PHASE2B_EVIDENCE),
            ),
            ModelEvidenceItem(label="Training data", value="26 synthetic rows", source=SFT_V2_MANIFEST),
            ModelEvidenceItem(
                label="Base → adapter F1",
                value=extraction,
                source=f"{_relative(PHASE2B_EVIDENCE)} (synthetic / medication / onset)",
            ),
            ModelEvidenceItem(
                label="False refusal",
                value=false_refusal,
                source=f"{_relative(PHASE2B_EVIDENCE)} (24-row confirmatory)",
            ),
            ModelEvidenceItem(
                label="Warm latency p50 / p95",
                value=warm_latency,
                source=_relative(PHASE2B_EVIDENCE),
            ),
            ModelEvidenceItem(
                label="Prompt ablation",
                value=str(prompt_decision.get("candidate_prompt", "UNKNOWN")),
                source=_relative(PHASE2B_EVIDENCE),
            ),
            ModelEvidenceItem(
                label="Evidence boundary",
                value="historical synthetic audit; not clinical validation",
                source=source,
            ),
        ],
    )


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Evidence artifact must be an object: {path}")
    return value


def _object(value: dict[str, Any], key: str) -> dict[str, Any]:
    nested = value.get(key)
    if not isinstance(nested, dict):
        raise ValueError(f"Evidence field must be an object: {key}")
    return nested


def _arm(frozen_run: dict[str, Any], name: str) -> dict[str, Any]:
    arms = frozen_run.get("arms")
    if not isinstance(arms, list):
        raise ValueError("Evidence field must be a list: frozen_run.arms")
    for arm in arms:
        if isinstance(arm, dict) and arm.get("name") == name:
            return arm
    raise ValueError(f"Required evidence arm is missing: {name}")


def _decimal(value: Any, places: int = 4) -> str:
    if not isinstance(value, (int, float)):
        raise ValueError("Evidence metric must be numeric")
    return f"{float(value):.{places}f}"


def _percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        raise ValueError("Evidence metric must be numeric")
    return f"{float(value) * 100:.2f}%"


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")
