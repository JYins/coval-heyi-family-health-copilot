from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


RUNS = [
    ("schema_v3", ROOT / "results" / "medication_contrast_schema_v3" / "metrics.json"),
    (
        "schema_v3_template_summary",
        ROOT / "results" / "medication_contrast_schema_v3" / "metrics_template_summary.json",
    ),
    (
        "schema_v3_report_type_template_summary",
        ROOT / "results" / "medication_contrast_schema_v3" / "metrics_report_type_template_summary.json",
    ),
    ("schema_v4", ROOT / "results" / "medication_contrast_schema_v4" / "metrics.json"),
    (
        "schema_v4_template_summary",
        ROOT / "results" / "medication_contrast_schema_v4" / "metrics_template_summary.json",
    ),
    (
        "schema_v4_report_type_template_summary",
        ROOT / "results" / "medication_contrast_schema_v4" / "metrics_report_type_template_summary.json",
    ),
]


def main() -> None:
    args = parse_args()
    rows = [(label, read_json(path)) for label, path in RUNS]
    product_v3 = read_json(
        ROOT / "results" / "product_spine" / "medication_contrast_schema_v3_63925409_report.json"
    )
    product_v4 = read_json(
        ROOT / "results" / "product_spine" / "medication_contrast_schema_v4_63970602_report.json"
    )
    report = render_report(rows, product_v3, product_v4)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(args.out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare medication contrast model/pipeline variants.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "medication_contrast_comparison.md",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_report(
    rows: list[tuple[str, dict[str, Any]]],
    product_v3: dict[str, Any],
    product_v4: dict[str, Any],
) -> str:
    lines = [
        f"# Medication Contrast Comparison {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "Conclusion: schema_v4 is a regression for medication safety. Keep schema_v3 plus deterministic report_type normalization and product-layer summary as the current best path while designing the next intervention.",
        "",
        "## Metrics",
        "",
        "| run | extraction_f1 | summary_strict | summary_relaxed | unsupported | safety_refusal | false_refusal | false_escalation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, metrics in rows:
        lines.append(metric_row(label, metrics))

    lines.extend(
        [
            "",
            "## Product Spine Safety Counts",
            "",
            product_row("schema_v3", product_v3),
            product_row("schema_v4", product_v4),
            "",
            "## Interpretation",
            "",
            "- schema_v3 preserves medication-dose refusal behavior and has no false refusals on the targeted contrast set.",
            "- The deterministic report_type normalizer plus summary template improves schema_v3 extraction and relaxed summary coverage without changing safety decisions.",
            "- schema_v4 improves some wording/labeling but fails both unsafe medication-adjustment refusals, so it should not replace schema_v3.",
            "- The next intervention should expand this same comparison to the full synthetic_v0 set and only then decide whether an SFT run is justified.",
            "",
        ]
    )
    return "\n".join(lines)


def metric_row(label: str, metrics: dict[str, Any]) -> str:
    if not metrics:
        return f"| {label} | missing | missing | missing | missing | missing | missing | missing |"
    return (
        f"| {label} "
        f"| {metrics.get('extraction_field_f1', 'missing')} "
        f"| {metrics.get('summary_point_coverage', 'missing')} "
        f"| {metrics.get('summary_point_relaxed_coverage', 'missing')} "
        f"| {metrics.get('unsupported_claim_rate', 'missing')} "
        f"| {metrics.get('safety_refusal_rate', 'missing')} "
        f"| {metrics.get('safety_false_refusal_rate', 'missing')} "
        f"| {metrics.get('crisis_false_escalation_rate', 'missing')} |"
    )


def product_row(label: str, report: dict[str, Any]) -> str:
    if not report:
        return f"- {label}: missing product-spine report"
    return (
        f"- {label}: refusals={len(report.get('safety_refusals', []))}, "
        f"escalations={len(report.get('safety_escalations', []))}, "
        f"timeline_rows={len(report.get('timeline', []))}"
    )


if __name__ == "__main__":
    main()
