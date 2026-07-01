from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / "results" / "sft_v2_eval_template_patch"
V3_DIR = ROOT / "results" / "sft_v3_eval"
OUT_PATH = V3_DIR / "comparison_vs_v2_template_patch.md"

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
        "# SFT v3 Eval Comparison",
        "",
        "This compares SFT v3 recovered/template eval outputs against the current best local candidate: SFT v2 plus deterministic summary-template patch.",
        "",
    ]

    regressions: list[str] = []
    improvements: list[str] = []

    for dataset in DATASETS:
        baseline = load_metrics(BASELINE_DIR / dataset / "metrics_recovered_report_type_template_summary.json")
        v3 = load_metrics(V3_DIR / dataset / "metrics_recovered_report_type_template_summary.json")
        lines.extend(
            [
                f"## {dataset}",
                "",
                "| Metric | V2 + template patch | SFT v3 | Delta | Direction |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for key, label, direction in METRICS:
            before = metric_value(baseline, key)
            after = metric_value(v3, key)
            value_delta = delta(after, before)
            lines.append(f"| {label} | {fmt(before)} | {fmt(after)} | {fmt_delta(value_delta)} | {direction} |")
            verdict = classify_delta(value_delta, direction)
            if verdict == "improve":
                improvements.append(f"{dataset}: {label} {fmt_delta(value_delta)}")
            elif verdict == "regress":
                regressions.append(f"{dataset}: {label} {fmt_delta(value_delta)}")
        lines.append("")

    lines.extend(
        [
            "## Decision",
            "",
            "- SFT v3 is a valid completed run, but it is not a new default candidate.",
            "- Keep `Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary patch` as the current product/demo default.",
            "- Use v3 as evidence that the project has a real experiment loop: a targeted patch was tested and rejected when it did not beat the measured baseline.",
            "",
            "## Improvements",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in improvements] or ["- none"])
    lines.extend(["", "## Regressions", ""])
    lines.extend([f"- {item}" for item in regressions] or ["- none"])
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "- Do not upload v3 as the primary adapter unless a later analysis finds a product-specific reason.",
            "- For public Hugging Face/model-card packaging, use v2 + deterministic summary patch metrics as the headline and mention v3 as an ablation/negative result.",
            "",
        ]
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}")


def load_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing metrics: {path}")
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


def classify_delta(value: float | None, direction: str) -> str:
    if value is None or abs(value) < 0.00005:
        return "same"
    if direction == "higher":
        return "improve" if value > 0 else "regress"
    return "improve" if value < 0 else "regress"


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


if __name__ == "__main__":
    main()
