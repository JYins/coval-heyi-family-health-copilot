from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    args = parse_args()
    metrics = read_json(args.metrics)
    details = read_json(args.details)
    predictions = read_jsonl(args.predictions) if args.predictions else []
    markdown = render_report(
        run_id=args.run_id,
        metrics=metrics,
        details=details,
        predictions=predictions,
        product_spine_status=args.product_spine_status,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(args.out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize baseline metrics and per-example failures.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, default=None)
    parser.add_argument("--product-spine-status", default="not run")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSONL file: {path}")
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Bad JSON in {path}:{line_no}") from exc
    return rows


def render_report(
    run_id: str,
    metrics: dict[str, Any],
    details: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    product_spine_status: str,
) -> str:
    failed = [row for row in details if row.get("outcome") == "fail"]
    lines = [
        f"# Baseline Summary: {run_id}",
        "",
        "## Metrics",
        "",
    ]
    for key in [
        "dataset_version",
        "example_count",
        "extraction_field_f1",
        "summary_point_coverage",
        "summary_point_relaxed_coverage",
        "unsupported_claim_rate",
        "safety_refusal_rate",
        "safety_false_refusal_rate",
        "crisis_escalation_recall",
        "crisis_false_escalation_rate",
        "hallucination_rate",
        "overdiagnosis_rate",
    ]:
        lines.append(f"- {key}: {metrics.get(key, 'missing')}")

    lines.extend(
        [
            "",
            "## Failure Overview",
            "",
            f"- failed_examples: {len(failed)} / {len(details)}",
            f"- product_spine_status: {product_spine_status}",
            f"- total_missing_fields: {sum(len(row.get('missing_fields', [])) for row in details)}",
            f"- total_extra_fields: {sum(len(row.get('extra_fields', [])) for row in details)}",
            f"- total_missing_summary_points: {sum(len(row.get('missing_summary_points', [])) for row in details)}",
            f"- safety_mismatches: {sum(bool(row.get('safety_mismatch')) for row in details)}",
            f"- crisis_mismatches: {sum(bool(row.get('crisis_mismatch')) for row in details)}",
            "",
            "## Worst Examples",
            "",
        ]
    )
    for row in worst_examples(details)[:5]:
        lines.extend(render_example(row, predictions))

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Treat these numbers as contract tests over synthetic/public-safe data, not clinical quality claims.",
            "- Large missing/extra field counts usually indicate schema adherence failure.",
            "- Safety/crisis mismatches should be prioritized even when extraction improves.",
            "",
        ]
    )
    return "\n".join(lines)


def worst_examples(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(details, key=failure_score, reverse=True)


def failure_score(row: dict[str, Any]) -> int:
    score = 0
    score += len(row.get("missing_fields", []))
    score += len(row.get("extra_fields", []))
    score += 2 * len(row.get("missing_summary_points", []))
    score += 5 if row.get("safety_mismatch") else 0
    score += 5 if row.get("crisis_mismatch") else 0
    return score


def render_example(row: dict[str, Any], predictions: list[dict[str, Any]]) -> list[str]:
    pred = next((item for item in predictions if item.get("id") == row.get("id")), {})
    structured = pred.get("structured", {})
    structured_keys = sorted(structured.keys()) if isinstance(structured, dict) else [type(structured).__name__]
    return [
        f"### {row.get('id')}",
        "",
        f"- input_type: {row.get('input_type')}",
        f"- failure_score: {failure_score(row)}",
        f"- structured_keys: {', '.join(structured_keys) if structured_keys else 'none'}",
        f"- missing_fields_sample: {short_list(row.get('missing_fields', []))}",
        f"- extra_fields_sample: {short_list(row.get('extra_fields', []))}",
        f"- missing_summary_points_sample: {short_list(row.get('missing_summary_points', []))}",
        f"- unsupported_claims: {short_list(row.get('unsupported_claims', []))}",
        f"- safety_mismatch: {row.get('safety_mismatch')}",
        f"- crisis_mismatch: {row.get('crisis_mismatch')}",
        "",
    ]


def short_list(values: list[Any], limit: int = 4) -> str:
    if not values:
        return "none"
    shown = [str(value) for value in values[:limit]]
    suffix = f" ... (+{len(values) - limit})" if len(values) > limit else ""
    return "; ".join(shown) + suffix


if __name__ == "__main__":
    main()
