from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DIR = ROOT / "results" / "sft_v2_eval"
PATCH_DIR = ROOT / "results" / "sft_v2_eval_template_patch"
OUT_PATH = PATCH_DIR / "comparison.md"

DATASETS = ["synthetic_v0", "medication_contrast_v0", "safety_onset_edge_v1_1"]
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


def main() -> None:
    lines = [
        "# SFT v2 Template Patch Comparison",
        "",
        "This compares the pulled Narval SFT v2 eval outputs against a local deterministic summary-template patch. No new model training is included in this comparison.",
        "",
    ]

    for dataset in DATASETS:
        original = load_metrics(ORIGINAL_DIR / dataset / "metrics_recovered_report_type_template_summary.json")
        patched = load_metrics(PATCH_DIR / dataset / "metrics_recovered_report_type_template_summary.json")
        contract = load_json(PATCH_DIR / dataset / "contract_validation_recovered_report_type_template_summary.json")
        product = load_json(PATCH_DIR / dataset / "product_spine_recovered_report.json")
        lines.extend(
            [
                f"## {dataset}",
                "",
                "| Metric | SFT v2 | V2 + template patch | Delta | Direction |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            before = metric_value(original, key)
            after = metric_value(patched, key)
            lines.append(f"| {label} | {fmt(before)} | {fmt(after)} | {fmt_delta(delta(after, before))} | {direction} |")

        counts = product_spine_counts(product)
        lines.extend(
            [
                "",
                f"Contract/product readiness: `{contract.get('product_spine_ready_count', 'missing')}/{contract.get('prediction_count', 'missing')}` product-spine ready.",
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
            "- The patch improves summary coverage by preserving medically relevant clauses from the original note while keeping safety guards explicit.",
            "- The patch does not change extraction fields; extraction deltas should remain zero.",
            "- If a future training run is needed, it should target remaining extraction/onset misses rather than the summary rendering gap.",
            "",
        ]
    )

    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_metrics(path: Path) -> dict[str, Any]:
    return load_json(path)


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
        "reports": len(report.get("timeline") or []),
        "lab_items": len(doctor_summary.get("lab_items") or []),
        "medications": len(doctor_summary.get("medications") or []),
        "symptoms": len(doctor_summary.get("symptoms") or []),
        "safety_escalations": len(report.get("safety_escalations") or []),
        "safety_refusals": len(report.get("safety_refusals") or []),
    }


if __name__ == "__main__":
    main()
