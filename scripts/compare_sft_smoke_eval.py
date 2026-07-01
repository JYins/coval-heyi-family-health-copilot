from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "sft_smoke_eval_64164883"
OUT_PATH = OUT_DIR / "comparison.md"

RUNS = [
    {
        "name": "synthetic_v0",
        "baseline_label": "schema_v3 + report_type + template summary",
        "adapter_label": "qwen7b_lora_sft_smoke_v0 + same postprocess",
        "baseline_metrics": ROOT / "results" / "baseline_schema_v3" / "metrics_report_type_template_summary.json",
        "adapter_metrics": OUT_DIR / "synthetic_v0" / "metrics_report_type_template_summary.json",
        "adapter_raw_metrics": OUT_DIR / "synthetic_v0" / "metrics_raw.json",
        "product_spine": OUT_DIR / "synthetic_v0" / "product_spine_report.json",
    },
    {
        "name": "medication_contrast_v0",
        "baseline_label": "schema_v3 + report_type + template summary",
        "adapter_label": "qwen7b_lora_sft_smoke_v0 + same postprocess",
        "baseline_metrics": ROOT
        / "results"
        / "medication_contrast_schema_v3"
        / "metrics_report_type_template_summary.json",
        "adapter_metrics": OUT_DIR / "medication_contrast_v0" / "metrics_report_type_template_summary.json",
        "adapter_raw_metrics": OUT_DIR / "medication_contrast_v0" / "metrics_raw.json",
        "product_spine": OUT_DIR / "medication_contrast_v0" / "product_spine_report.json",
    },
]

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


def main() -> None:
    lines = [
        "# SFT Smoke Eval Comparison",
        "",
        "Run: `qwen7b_lora_sft_smoke_v0`",
        "",
        "Adapter training job: `64164883`.",
        "Adapter eval job: `64167387`.",
        "",
        "This report compares the completed adapter eval against the current product baseline. "
        "All rows use synthetic/public eval data only.",
        "",
    ]

    for run in RUNS:
        baseline = load_json(run["baseline_metrics"])
        adapter = load_json(run["adapter_metrics"])
        raw = load_json(run["adapter_raw_metrics"])
        product = load_json(run["product_spine"])

        lines.extend(
            [
                f"## {run['name']}",
                "",
                f"Baseline: {run['baseline_label']}.",
                f"Adapter: {run['adapter_label']}.",
                "",
                "| Metric | Baseline | Adapter | Delta | Direction |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            before = metric_value(baseline, key)
            after = metric_value(adapter, key)
            delta = None if before is None or after is None else after - before
            lines.append(
                f"| {label} | {fmt(before)} | {fmt(after)} | {fmt_delta(delta)} | {direction} |"
            )

        lines.extend(
            [
                "",
                "Raw adapter metrics before deterministic postprocess:",
                "",
                "| Metric | Raw adapter |",
                "| --- | ---: |",
            ]
        )
        for key, label, _direction in METRICS:
            lines.append(f"| {label} | {fmt(metric_value(raw, key))} |")

        spine = product_spine_counts(product)
        lines.extend(
            [
                "",
                "Adapter product-spine smoke:",
                "",
                f"- Timeline rows: {spine['timeline_rows']}",
                f"- Lab items: {spine['lab_items']}",
                f"- Symptoms: {spine['symptoms']}",
                f"- Safety escalations: {spine['safety_escalations']}",
                f"- Safety refusals: {spine['safety_refusals']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation",
            "",
            "- The smoke adapter is a small positive result on `synthetic_v0` after the deterministic product layer: extraction F1, strict summary coverage, and relaxed summary coverage all improve slightly, and the previous synthetic false refusal drops to 0.0.",
            "- The adapter is neutral on `medication_contrast_v0` after postprocess: extraction, summary, refusal, false-refusal, and false-escalation metrics match the current schema_v3 product baseline.",
            "- Safety gates remain intact on these evals: medication contrast refusal stays 1.0, medication contrast false refusal stays 0.0, synthetic crisis recall stays 1.0, and hallucination/overdiagnosis stay 0.0.",
            "- This is not enough evidence for a broad sweep. The next safe improvement is failure-driven data or constrained label normalization for the remaining report-type/product-spine label issues.",
            "",
            "## Next Safe Step",
            "",
            "Add targeted synthetic training/eval examples for the remaining report-type failures (`ultrasound`, `lab_items`, and symptom-note labels) and rerun a single slightly larger SFT v1 only after those examples pass the same leakage/privacy validator.",
            "",
        ]
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing required comparison input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def metric_value(metrics: dict, key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    return float(value)


def fmt(value: float | None) -> str:
    if value is None:
        return "missing"
    return f"{value:.4f}"


def fmt_delta(value: float | None) -> str:
    if value is None:
        return "missing"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.4f}"


def product_spine_counts(report: dict) -> dict[str, int]:
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
