from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "sft_v2_eval"
OUT_PATH = OUT_DIR / "comparison.md"

METRICS = [
    ("extraction_field_f1", "Extraction F1", "higher"),
    ("summary_point_coverage", "Summary strict", "higher"),
    ("summary_point_relaxed_coverage", "Summary relaxed", "higher"),
    ("unsupported_claim_rate", "Unsupported claim", "lower"),
    ("safety_refusal_rate", "Safety refusal", "higher"),
    ("safety_false_refusal_rate", "False refusal", "lower"),
    ("crisis_escalation_recall", "Crisis recall", "higher"),
    ("crisis_false_escalation_rate", "False escalation", "lower"),
    ("hallucination_rate", "Hallucination", "lower"),
    ("overdiagnosis_rate", "Overdiagnosis", "lower"),
]

RUNS = [
    {
        "name": "synthetic_v0",
        "baseline": ROOT / "results" / "baseline_schema_v3" / "metrics_report_type_template_summary.json",
        "v1": ROOT / "results" / "sft_v1_eval" / "synthetic_v0" / "metrics_report_type_template_summary.json",
        "v1_constrained": ROOT
        / "results"
        / "sft_v1_eval_constrained"
        / "synthetic_v0"
        / "metrics_report_type_template_summary.json",
        "v2": OUT_DIR / "synthetic_v0" / "metrics_recovered_report_type_template_summary.json",
        "product_spine": OUT_DIR / "synthetic_v0" / "product_spine_recovered_report.json",
    },
    {
        "name": "medication_contrast_v0",
        "baseline": ROOT
        / "results"
        / "medication_contrast_schema_v3"
        / "metrics_report_type_template_summary.json",
        "v1": ROOT
        / "results"
        / "sft_v1_eval"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json",
        "v1_constrained": ROOT
        / "results"
        / "sft_v1_eval_constrained"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json",
        "v2": OUT_DIR / "medication_contrast_v0" / "metrics_recovered_report_type_template_summary.json",
        "product_spine": OUT_DIR / "medication_contrast_v0" / "product_spine_recovered_report.json",
    },
    {
        "name": "safety_onset_edge_v1_1",
        "baseline": ROOT / "results" / "safety_onset_edge_v1_1" / "metrics.json",
        "v1": ROOT
        / "results"
        / "sft_v1_eval_v1_1"
        / "safety_onset_edge_v1_1"
        / "metrics_recovered_report_type_template_summary.json",
        "v1_constrained": None,
        "v2": OUT_DIR / "safety_onset_edge_v1_1" / "metrics_recovered_report_type_template_summary.json",
        "product_spine": OUT_DIR / "safety_onset_edge_v1_1" / "product_spine_recovered_report.json",
    },
]


def main() -> None:
    trainer_state = load_json(ROOT / "results" / "sft_v2" / "trainer_state.json")
    manifest = load_json(ROOT / "results" / "sft_v2" / "sft_run_manifest.json")
    final_train = final_train_metrics(trainer_state)
    final_eval = final_eval_metrics(trainer_state)

    lines = [
        "# SFT v2 Eval Comparison",
        "",
        "Run: `qwen7b_lora_sft_v2`",
        "",
        "Training job: `64289666`.",
        "Eval job: `64330400`.",
        "",
        "All rows are synthetic/public. V2 uses a 26-row failure-driven patch set and is compared on held-out gold files only.",
        "",
        "## Training Signal",
        "",
        f"- Base model: `{manifest.get('base_model', 'missing')}`",
        f"- Final train loss: {fmt(final_train.get('train_loss', final_train.get('loss')))}",
        f"- Eval loss: {fmt(final_eval.get('eval_loss'))}",
        f"- Eval mean token accuracy: {fmt(final_eval.get('eval_mean_token_accuracy'))}",
        f"- Global steps: {trainer_state.get('global_step', 'missing')}",
        "",
    ]

    for run in RUNS:
        baseline = load_json(run["baseline"])
        v1 = load_json(run["v1"])
        v1_constrained = load_json(run["v1_constrained"]) if run["v1_constrained"] else None
        v2 = load_json(run["v2"])
        product = load_json(run["product_spine"])

        lines.extend(
            [
                f"## {run['name']}",
                "",
                "| Metric | Baseline | SFT v1 | V1 constrained | SFT v2 | v2-baseline | v2-v1 | Direction |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            base_value = metric_value(baseline, key)
            v1_value = metric_value(v1, key)
            v1c_value = metric_value(v1_constrained, key) if v1_constrained else None
            v2_value = metric_value(v2, key)
            lines.append(
                f"| {label} | {fmt(base_value)} | {fmt(v1_value)} | {fmt(v1c_value)} | "
                f"{fmt(v2_value)} | {fmt_delta(delta(v2_value, base_value))} | "
                f"{fmt_delta(delta(v2_value, v1_value))} | {direction} |"
            )

        counts = product_spine_counts(product)
        lines.extend(
            [
                "",
                "V2 product-spine smoke:",
                "",
                f"- Reports: {counts['reports']}",
                f"- Lab items: {counts['lab_items']}",
                f"- Medications: {counts['medications']}",
                f"- Symptoms: {counts['symptoms']}",
                f"- Safety escalations: {counts['safety_escalations']}",
                f"- Safety refusals: {counts['safety_refusals']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation",
            "",
            "- Treat v2 as a candidate adapter until this report is reviewed against per-example failures.",
            "- If v2 improves the v1.1 onset/safety slice without regressing synthetic_v0 or medication_contrast_v0, the next step is a tiny ablation or constrained decoding integration.",
            "- If v2 regresses safety or product-spine readiness, keep v1/v1-constrained as the resume-safe artifact and use the per-example details to patch data instead of scaling training.",
            "",
        ]
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"missing comparison input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def final_train_metrics(state: dict[str, Any]) -> dict[str, Any]:
    history = state.get("log_history") or []
    for row in reversed(history):
        if "train_loss" in row:
            return row
    for row in reversed(history):
        if "loss" in row:
            return row
    return {}


def final_eval_metrics(state: dict[str, Any]) -> dict[str, Any]:
    history = state.get("log_history") or []
    for row in reversed(history):
        if "eval_loss" in row:
            return row
    return {}


def metric_value(metrics: dict[str, Any] | None, key: str) -> float | None:
    if not metrics:
        return None
    value = metrics.get(key)
    if value is None:
        return None
    return float(value)


def delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return after - before


def fmt(value: Any) -> str:
    if value is None:
        return "missing"
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return str(value)


def fmt_delta(value: float | None) -> str:
    if value is None:
        return "missing"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.4f}"


def product_spine_counts(report: dict[str, Any]) -> dict[str, int]:
    doctor_summary = report.get("doctor_summary") or {}
    return {
        "reports": len(report.get("timeline") or []),
        "lab_items": len(doctor_summary.get("lab_items") or []),
        "medications": len(doctor_summary.get("medications") or []),
        "symptoms": len(doctor_summary.get("symptoms") or []),
        "safety_escalations": len(report.get("safety_escalations") or []),
        "safety_refusals": len(report.get("safety_refusals") or []),
    }


if __name__ == "__main__":
    main()
