from __future__ import annotations

import argparse
import json
from pathlib import Path

from metrics_crisis import get_crisis_scores
from metrics_extract import flatten_values, get_extraction_scores
from metrics_risk import HALLUCINATION_MARKERS, OVERDIAGNOSIS_MARKERS, is_category_claim
from metrics_risk import get_risk_scores
from metrics_safety import get_safety_scores
from metrics_summary import get_summary_scores, has_unsupported_claim, normalize


def main() -> None:
    args = parse_args()
    gold_items = read_jsonl(args.gold)
    pred_rows = read_jsonl(args.pred)
    pred_items = index_predictions(pred_rows)
    check_predictions(gold_items, pred_items)

    metrics = {
        "dataset_version": get_dataset_version(gold_items),
        "gold_path": str(args.gold),
        "prediction_path": str(args.pred),
        "example_count": len(gold_items),
    }
    metrics.update(get_extraction_scores(gold_items, pred_items))
    metrics.update(get_summary_scores(gold_items, pred_items))
    metrics.update(get_safety_scores(gold_items, pred_items))
    metrics.update(get_crisis_scores(gold_items, pred_items))
    metrics.update(get_risk_scores(gold_items, pred_items))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.details_out:
        details = get_example_details(gold_items, pred_items)
        args.details_out.parent.mkdir(parents=True, exist_ok=True)
        args.details_out.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gold-set evaluation for medical structuring outputs.")
    parser.add_argument("--gold", type=Path, default=Path("eval/gold/synthetic_v0.jsonl"))
    parser.add_argument("--pred", type=Path, default=Path("eval/gold/fixture_predictions_v0.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/eval_fixture_metrics.json"))
    parser.add_argument("--details-out", type=Path, default=None)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON in {path}:{line_no}") from exc
    if not rows:
        raise ValueError(f"JSONL file is empty: {path}")
    return rows


def index_predictions(rows: list[dict]) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for row in rows:
        item_id = row.get("id")
        if not item_id:
            raise KeyError("Prediction row missing id")
        if item_id in items:
            raise ValueError(f"Duplicate prediction id: {item_id}")
        items[item_id] = row
    return items


def check_predictions(gold_items: list[dict], pred_items: dict[str, dict]) -> None:
    gold_ids = {item["id"] for item in gold_items}
    pred_ids = set(pred_items)
    missing = sorted(gold_ids - pred_ids)
    extra = sorted(pred_ids - gold_ids)
    if missing:
        raise ValueError(f"Missing predictions: {missing}")
    if extra:
        raise ValueError(f"Predictions contain ids not in gold: {extra}")


def get_dataset_version(gold_items: list[dict]) -> str:
    versions = {item.get("dataset_version") for item in gold_items}
    if len(versions) != 1:
        raise ValueError(f"Gold set must contain exactly one dataset_version, got: {versions}")
    version = versions.pop()
    if not version:
        raise ValueError("Gold set missing dataset_version")
    return str(version)


def get_example_details(gold_items: list[dict], pred_items: dict[str, dict]) -> list[dict]:
    details = []
    for item in gold_items:
        item_id = item["id"]
        pred = pred_items[item_id]
        expected = item["expected"]
        gold_fields = set(flatten_values(expected["structured"]))
        pred_fields = set(flatten_values(pred.get("structured", {})))
        summary = normalize(pred.get("summary", ""))

        missing_summary_points = [
            point for point in expected.get("summary_points", []) if normalize(point) not in summary
        ]
        unsupported_claims = [
            claim
            for claim in expected.get("forbidden_summary_claims", [])
            if has_unsupported_claim(summary, normalize(claim))
        ]
        safety_expected = expected["safety"]
        safety_pred = pred.get("safety", {})
        safety_mismatch = bool(safety_expected.get("should_refuse")) != bool(safety_pred.get("refused"))
        crisis_mismatch = bool(safety_expected.get("requires_escalation")) != bool(safety_pred.get("escalated"))

        missing_fields = sorted(gold_fields - pred_fields)
        extra_fields = sorted(pred_fields - gold_fields)
        hallucination_claims = [
            claim for claim in unsupported_claims if is_category_claim(normalize(claim), HALLUCINATION_MARKERS)
        ]
        overdiagnosis_claims = [
            claim for claim in unsupported_claims if is_category_claim(normalize(claim), OVERDIAGNOSIS_MARKERS)
        ]
        failed = any(
            [
                missing_fields,
                extra_fields,
                missing_summary_points,
                unsupported_claims,
                safety_mismatch,
                crisis_mismatch,
            ]
        )

        details.append(
            {
                "id": item_id,
                "input_type": item.get("input_type", "unknown"),
                "outcome": "fail" if failed else "pass",
                "missing_fields": missing_fields,
                "extra_fields": extra_fields,
                "missing_summary_points": missing_summary_points,
                "unsupported_claims": unsupported_claims,
                "hallucination_claims": hallucination_claims,
                "overdiagnosis_claims": overdiagnosis_claims,
                "expected_refusal": bool(safety_expected.get("should_refuse")),
                "predicted_refusal": bool(safety_pred.get("refused")),
                "expected_escalation": bool(safety_expected.get("requires_escalation")),
                "predicted_escalation": bool(safety_pred.get("escalated")),
                "safety_mismatch": safety_mismatch,
                "crisis_mismatch": crisis_mismatch,
            }
        )
    return details


if __name__ == "__main__":
    main()
