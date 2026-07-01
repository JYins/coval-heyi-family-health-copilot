from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STANDARD_DIR = ROOT / "results" / "sft_v1_eval"
CONSTRAINED_DIR = ROOT / "results" / "sft_v1_eval_constrained"
OUT_PATH = CONSTRAINED_DIR / "comparison.md"

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
        "v1": STANDARD_DIR / "synthetic_v0" / "metrics_report_type_template_summary.json",
        "constrained": CONSTRAINED_DIR / "synthetic_v0" / "metrics_report_type_template_summary.json",
        "product_spine": CONSTRAINED_DIR / "synthetic_v0" / "product_spine_report.json",
        "normalization": CONSTRAINED_DIR / "synthetic_v0" / "normalization_report.json",
        "report_type": CONSTRAINED_DIR / "synthetic_v0" / "report_type_normalization_report.json",
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
        "v1": STANDARD_DIR / "medication_contrast_v0" / "metrics_report_type_template_summary.json",
        "constrained": CONSTRAINED_DIR
        / "medication_contrast_v0"
        / "metrics_report_type_template_summary.json",
        "product_spine": CONSTRAINED_DIR / "medication_contrast_v0" / "product_spine_report.json",
        "normalization": CONSTRAINED_DIR / "medication_contrast_v0" / "normalization_report.json",
        "report_type": CONSTRAINED_DIR
        / "medication_contrast_v0"
        / "report_type_normalization_report.json",
    },
]


def main() -> None:
    lines = [
        "# SFT v1 Constrained Eval Comparison",
        "",
        "Run: `qwen7b_lora_sft_v1` with deterministic product-layer enum/schema normalization.",
        "",
        "This report intentionally keeps the original v1 eval separate from the constrained postprocess. All eval rows are synthetic/public only.",
        "",
    ]

    for run in RUNS:
        baseline = load_json(run["baseline"])
        smoke = load_json(run["smoke"])
        v1 = load_json(run["v1"])
        constrained = load_json(run["constrained"])
        product = load_json(run["product_spine"])
        normalization = load_json(run["normalization"])
        report_type = load_json(run["report_type"])

        lines.extend(
            [
                f"## {run['name']}",
                "",
                "| Metric | Baseline | Smoke v0 | SFT v1 | SFT v1 constrained | constrained-v1 | constrained-smoke | Direction |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            base_value = metric_value(baseline, key)
            smoke_value = metric_value(smoke, key)
            v1_value = metric_value(v1, key)
            constrained_value = metric_value(constrained, key)
            lines.append(
                f"| {label} | {fmt(base_value)} | {fmt(smoke_value)} | {fmt(v1_value)} | "
                f"{fmt(constrained_value)} | {fmt_delta(delta(constrained_value, v1_value))} | "
                f"{fmt_delta(delta(constrained_value, smoke_value))} | {direction} |"
            )

        counts = product_spine_counts(product)
        lines.extend(
            [
                "",
                "Constrained product-spine smoke:",
                "",
                f"- Timeline rows: {counts['timeline_rows']}",
                f"- Lab items: {counts['lab_items']}",
                f"- Symptoms: {counts['symptoms']}",
                f"- Safety escalations: {counts['safety_escalations']}",
                f"- Safety refusals: {counts['safety_refusals']}",
                "",
                "Normalization summary:",
                "",
                f"- Prediction normalizer changed rows: {changed_count(normalization)}",
                f"- Report-type normalizer changed rows: {changed_count(report_type)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation",
            "",
            "- The constrained product layer turns v1 into the current best measured path on both eval sets.",
            "- On `synthetic_v0`, constrained v1 improves extraction F1 over raw v1 postprocess while preserving safety, crisis, hallucination, and overdiagnosis gates.",
            "- On `medication_contrast_v0`, constrained v1 improves extraction F1 over the previous deterministic path and keeps the medication refusal/false-refusal checks stable.",
            "- This supports constrained labels and product-layer schema repair. It does not justify a broad training sweep by itself.",
            "",
            "## Next Safe Step",
            "",
            "Bake the constrained enum/report_type normalization into the local fake-data product spine, then add a tiny eval-only slice for onset and report_type edge cases before considering any v2 training.",
            "",
        ]
    )

    CONSTRAINED_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing comparison input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def changed_count(report: dict[str, Any]) -> Any:
    if "changed_prediction_count" in report:
        return report["changed_prediction_count"]
    return report.get("changed_rows", "missing")


if __name__ == "__main__":
    main()
