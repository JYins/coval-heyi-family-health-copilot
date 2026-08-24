from __future__ import annotations

import json
from pathlib import Path

from .api_schemas import ModelEvidenceItem, ModelEvidenceResponse


ROOT = Path(__file__).resolve().parents[2]
V1_1_METRICS = ROOT / "results" / "sft_v1_eval_v1_1" / "safety_onset_edge_v1_1" / "metrics_recovered_report_type_template_summary.json"
V2_COMPARISON = ROOT / "results" / "sft_v2_eval" / "comparison.md"
V2_METRICS = ROOT / "results" / "sft_v2_eval" / "safety_onset_edge_v1_1" / "metrics_recovered_report_type_template_summary.json"
V2_PATCH_METRICS = ROOT / "results" / "sft_v2_eval_template_patch" / "safety_onset_edge_v1_1" / "metrics_recovered_report_type_template_summary.json"
V3_COMPARISON = ROOT / "results" / "sft_v3_eval" / "comparison_vs_v2_template_patch.md"


def model_evidence() -> ModelEvidenceResponse:
    source_path = V1_1_METRICS
    metrics = _load_metrics(source_path)
    status = "sft_v1_1_evidence_available"
    adapter = "LoRA SFT v1.1"
    if V2_METRICS.exists() and V2_COMPARISON.exists():
        source_path = V2_METRICS
        metrics = _load_metrics(source_path)
        status = "sft_v2_eval_available"
        adapter = "LoRA SFT v2 candidate"
    if V2_PATCH_METRICS.exists():
        source_path = V2_PATCH_METRICS
        metrics = _load_metrics(source_path)
        status = "sft_v2_template_patch_available"
        adapter = "LoRA SFT v2 + deterministic summary patch"
    if V2_PATCH_METRICS.exists() and V3_COMPARISON.exists():
        status = "sft_v3_ablation_complete_keep_v2_template_patch"

    source = _relative(source_path)
    items = [
        ModelEvidenceItem(label="Training data", value="26 synthetic rows", source="data/public/sft_v2/manifest.json"),
        ModelEvidenceItem(label="Extraction F1", value=_metric(metrics.get("extraction_field_f1")), source=source),
        ModelEvidenceItem(label="Summary strict", value=_metric(metrics.get("summary_point_coverage")), source=source),
        ModelEvidenceItem(label="Summary relaxed", value=_metric(metrics.get("summary_point_relaxed_coverage")), source=source),
        ModelEvidenceItem(label="Safety refusal", value=_percent(metrics.get("safety_refusal_rate")), source=source),
        ModelEvidenceItem(label="Crisis recall", value=_percent(metrics.get("crisis_escalation_recall")), source=source),
        ModelEvidenceItem(
            label="Hallucination / overdiagnosis",
            value=f"{_percent(metrics.get('hallucination_rate'))} / {_percent(metrics.get('overdiagnosis_rate'))}",
            source=source,
        ),
        ModelEvidenceItem(label="RAG phase", value="retrieval scaffold only", source="results/rag_v0/metrics.json"),
    ]
    if V3_COMPARISON.exists():
        items.append(ModelEvidenceItem(label="Latest ablation", value="SFT v3 completed; not adopted", source=_relative(V3_COMPARISON)))
    return ModelEvidenceResponse(
        base_model="Qwen/Qwen2.5-7B-Instruct", adapter=adapter, status=status, metrics=items
    )


def _load_metrics(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in data.items() if isinstance(value, (int, float))}


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _metric(value: float | None) -> str:
    return "not run" if value is None else f"{value:.4f}"


def _percent(value: float | None) -> str:
    return "not run" if value is None else f"{value * 100:.0f}%"
