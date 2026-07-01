from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SLICE_DIR = ROOT / "results" / "sft_v1_eval_v1_1" / "safety_onset_edge_v1_1"
OUT_DIR = ROOT / "results" / "progress"


def main() -> None:
    now = datetime.now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    details = read_json(SLICE_DIR / "example_details_recovered_report_type_template_summary.json")
    metrics = read_json(SLICE_DIR / "metrics_recovered_report_type_template_summary.json")
    recovery = read_json(SLICE_DIR / "recovery_report.json")

    report = render_report(now, details, metrics, recovery)
    out_path = OUT_DIR / f"sft_v1_1_gap_summary_{now:%Y%m%d_%H%M%S}.md"
    out_path.write_text(report, encoding="utf-8")
    (OUT_DIR / "latest_sft_v1_1_gap_summary.md").write_text(report, encoding="utf-8")
    print(out_path)


def render_report(now: datetime, details: list[dict[str, Any]], metrics: dict[str, Any], recovery: dict[str, Any]) -> str:
    missing_field_counts = Counter()
    extra_field_counts = Counter()
    missing_summary_counts = Counter()
    failed_ids: list[str] = []
    for row in details:
        if row.get("outcome") != "pass":
            failed_ids.append(str(row.get("id", "missing")))
        for value in row.get("missing_fields") or []:
            missing_field_counts[classify_field(str(value))] += 1
        for value in row.get("extra_fields") or []:
            extra_field_counts[classify_field(str(value))] += 1
        missing_summary_counts[str(row.get("id", "missing"))] = len(row.get("missing_summary_points") or [])

    lines = [
        f"# SFT v1.1 Gap Summary {now:%Y-%m-%d %H:%M:%S}",
        "",
        "Scope: recovered predictions for `safety_onset_edge_v1_1` only.",
        "",
        "## Current Metrics",
        "",
        metric_line(metrics, "example_count"),
        metric_line(metrics, "extraction_field_f1"),
        metric_line(metrics, "summary_point_coverage"),
        metric_line(metrics, "summary_point_relaxed_coverage"),
        metric_line(metrics, "unsupported_claim_rate"),
        metric_line(metrics, "safety_refusal_rate"),
        metric_line(metrics, "safety_false_refusal_rate"),
        metric_line(metrics, "crisis_escalation_recall"),
        metric_line(metrics, "crisis_false_escalation_rate"),
        metric_line(metrics, "hallucination_rate"),
        metric_line(metrics, "overdiagnosis_rate"),
        "",
        "## Recovery Status",
        "",
        f"- parse_error_count: {recovery.get('parse_error_count', 'missing') if recovery else 'missing'}",
        f"- json_repair_applied_count: {recovery.get('json_repair_applied_count', 'missing') if recovery else 'missing'}",
        "",
        "## Remaining Gap Shape",
        "",
        f"- failed_or_partial_examples: {len(failed_ids)}/{len(details)}",
        f"- failed_or_partial_ids: {', '.join(failed_ids) if failed_ids else 'none'}",
        counter_line("missing_field_groups", missing_field_counts),
        counter_line("extra_field_groups", extra_field_counts),
        counter_line("missing_summary_points_by_id", missing_summary_counts),
        "",
        "## Interpretation",
        "",
        "- The hard slice is now an extraction/summary-quality problem, not a JSON-validity or safety-gate problem.",
        "- Remaining structured misses cluster around symptom onset/detail granularity and one extra appointment type.",
        "- The next experiment should be a small failure-driven patch or constrained decoding check, not a broad training sweep.",
        "",
    ]
    return "\n".join(lines)


def classify_field(value: str) -> str:
    if value.startswith("symptoms[") and ".onset=" in value:
        return "symptom_onset"
    if value.startswith("symptoms[") and ".text=" in value:
        return "symptom_text"
    if value.startswith("medications["):
        return "medication"
    if value.startswith("appointments["):
        return "appointment"
    if value.startswith("patient."):
        return "patient"
    return "other"


def metric_line(metrics: dict[str, Any], key: str) -> str:
    return f"- {key}: {metrics.get(key, 'missing') if metrics else 'missing'}"


def counter_line(label: str, counter: Counter[str]) -> str:
    if not counter:
        return f"- {label}: none"
    values = ", ".join(f"{key}={value}" for key, value in counter.most_common())
    return f"- {label}: {values}"


def read_json(path: Path) -> Any:
    if not path.exists():
        return [] if "example_details" in path.name else {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
