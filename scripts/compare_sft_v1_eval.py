from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "sft_v1_eval"
OUT_PATH = OUT_DIR / "comparison.md"

METRICS = [
    ("extraction_field_f1", "Extraction F1", "higher"),
    ("summary_point_coverage", "Summary strict", "higher"),
    ("summary_point_relaxed_coverage", "Summary relaxed", "higher"),
    ("unsupported_claim_rate", "Unsupported claim rate", "lower"),
    ("safety_refusal_rate", "Safety refusal", "higher"),
    ("safety_false_refusal_rate", "Safety false refusal", "lower"),
    ("crisis_escalation_recall", "Crisis recall", "higher"),
    ("crisis_false_escalation_rate", "Crisis false escalation", "lower"),
    ("hallucination_rate", "Hallucination rate", "lower"),
    ("overdiagnosis_rate", "Overdiagnosis rate", "lower"),
]

RUNS = [
    {
        "name": "synthetic_v0",
        "baseline": ROOT / "results" / "baseline_schema_v3" / "metrics_report_type_template_summary.json",
        "smoke": ROOT
        / "results"
        / "sft_smoke_eval_64164883"
        / "synthetic_v0"
        / "metrics_report_type_template_summary.json",
        "v1": OUT_DIR / "synthetic_v0" / "metrics_report_type_template_summary.json",
        "v1_raw": OUT_DIR / "synthetic_v0" / "metrics_raw.json",
        "product_spine": OUT_DIR / "synthetic_v0" / "product_spine_report.json",
    },
    {
        "name": "medication_contrast_v0",
        "baseline": ROOT
        / "results"
        / "medication_contrast_schema_v3"
        / "metrics_report_type_template_summary.json",
        "smoke": ROOT
        / "results"
        / "sft_smoke_eval_64164883"
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json",
        "v1": OUT_DIR / "medication_contrast_v0" / "metrics_report_type_template_summary.json",
        "v1_raw": OUT_DIR / "medication_contrast_v0" / "metrics_raw.json",
        "product_spine": OUT_DIR / "medication_contrast_v0" / "product_spine_report.json",
    },
]


def main() -> None:
    trainer_state = load_json(ROOT / "results" / "sft_v1" / "trainer_state.json")
    final_train = final_train_metrics(trainer_state)
    final_eval = final_eval_metrics(trainer_state)

    lines = [
        "# SFT v1 Eval Comparison",
        "",
        "Run: `qwen7b_lora_sft_v1`",
        "",
        "Training job: `64180690`.",
        "Eval job: `64181449`.",
        "",
        "This report compares the failure-driven v1 adapter against both the current schema_v3 product baseline and the earlier smoke adapter. All eval rows are synthetic/public only.",
        "",
        "## Training Signal",
        "",
        f"- Final step train loss: {fmt(final_train.get('train_loss', final_train.get('loss')))}",
        f"- Eval loss: {fmt(final_eval.get('eval_loss'))}",
        f"- Eval mean token accuracy: {fmt(final_eval.get('eval_mean_token_accuracy'))}",
        f"- Global steps: {trainer_state.get('global_step', 'missing')}",
        "",
    ]

    for run in RUNS:
        baseline = load_json(run["baseline"])
        smoke = load_json(run["smoke"])
        v1 = load_json(run["v1"])
        raw = load_json(run["v1_raw"])
        product = load_json(run["product_spine"])
        lines.extend(
            [
                f"## {run['name']}",
                "",
                "| Metric | Baseline | Smoke v0 | SFT v1 | v1-baseline | v1-smoke | Direction |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            base_value = metric_value(baseline, key)
            smoke_value = metric_value(smoke, key)
            v1_value = metric_value(v1, key)
            lines.append(
                f"| {label} | {fmt(base_value)} | {fmt(smoke_value)} | {fmt(v1_value)} | "
                f"{fmt_delta(delta(v1_value, base_value))} | {fmt_delta(delta(v1_value, smoke_value))} | {direction} |"
            )

        lines.extend(
            [
                "",
                "Raw v1 adapter metrics before deterministic postprocess:",
                "",
                "| Metric | Raw v1 |",
                "| --- | ---: |",
            ]
        )
        for key, label, _direction in METRICS:
            lines.append(f"| {label} | {fmt(metric_value(raw, key))} |")

        counts = product_spine_counts(product)
        lines.extend(
            [
                "",
                "V1 product-spine smoke:",
                "",
                f"- Timeline rows: {counts['timeline_rows']}",
                f"- Lab items: {counts['lab_items']}",
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
            "- V1 preserved the safety gates on these evals, but it did not beat smoke v0 on the main held-out metrics.",
            "- On `synthetic_v0`, v1 remains slightly above the schema_v3 product baseline on extraction and keeps the smoke-level summary/safety behavior, but extraction F1 is slightly lower than smoke v0.",
            "- On `medication_contrast_v0`, v1 is neutral after deterministic postprocess and matches both smoke v0 and the schema_v3 product baseline.",
            "- The improved training/eval loss is not enough to claim product improvement. The next step should be better eval coverage or constrained report_type decoding, not a larger sweep.",
            "",
            "## Next Safe Step",
            "",
            "Inspect per-example failures for `synthetic_v0` report_type and field extraction, then decide whether to add a small new eval slice before any more training.",
            "",
        ]
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_json(path: Path) -> dict[str, Any]:
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


def metric_value(metrics: dict[str, Any], key: str) -> float | None:
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
        "timeline_rows": len(report.get("timeline") or []),
        "lab_items": len(doctor_summary.get("lab_items") or []),
        "symptoms": len(doctor_summary.get("symptoms") or []),
        "safety_escalations": len(report.get("safety_escalations") or []),
        "safety_refusals": len(report.get("safety_refusals") or []),
    }


if __name__ == "__main__":
    main()
