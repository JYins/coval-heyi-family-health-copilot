from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STRUCTURED_KEYS = {
    "patient",
    "report_date",
    "hospital",
    "report_type",
    "lab_items",
    "medications",
    "symptoms",
}


def main() -> None:
    args = parse_args()
    rows = read_jsonl(args.predictions)
    report = validate_rows(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate model predictions against the product JSON contract.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSONL file: {path}")
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Bad JSON in {path}:{line_no}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Prediction row must be an object at {path}:{line_no}")
        rows.append(row)
    if not rows:
        raise ValueError(f"Prediction file is empty: {path}")
    return rows


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    details = [validate_one(row) for row in rows]
    return {
        "prediction_count": len(rows),
        "valid_contract_count": sum(not detail["issues"] for detail in details),
        "invalid_contract_count": sum(bool(detail["issues"]) for detail in details),
        "product_spine_ready_count": sum(detail["product_spine_ready"] for detail in details),
        "evaluable_count": sum(detail["evaluable"] for detail in details),
        "details": details,
    }


def validate_one(row: dict[str, Any]) -> dict[str, Any]:
    issues = []
    item_id = row.get("id")
    if not isinstance(item_id, str) or not item_id:
        issues.append("missing id")

    structured = row.get("structured")
    if not isinstance(structured, dict):
        issues.append("structured is not an object")
        structured = {}

    missing_keys = sorted(REQUIRED_STRUCTURED_KEYS - set(structured))
    if missing_keys:
        issues.append("structured missing keys: " + ", ".join(missing_keys))

    summary = row.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        issues.append("summary is empty or not a string")

    safety = row.get("safety")
    if not isinstance(safety, dict):
        issues.append("safety is not an object")
    else:
        if not isinstance(safety.get("refused"), bool):
            issues.append("safety.refused is not boolean")
        if not isinstance(safety.get("escalated"), bool):
            issues.append("safety.escalated is not boolean")

    issues.extend(validate_rows_of_objects(structured, "lab_items", "name"))
    issues.extend(validate_rows_of_objects(structured, "medications", "name"))
    issues.extend(validate_rows_of_objects(structured, "symptoms", "text"))
    issues.extend(validate_rows_of_objects(structured, "appointments", None))
    issues.extend(validate_rows_of_objects(structured, "findings", "name"))

    product_issues = [issue for issue in issues if not is_product_spine_compatible(issue)]
    return {
        "id": item_id or "missing",
        "issues": issues,
        "evaluable": isinstance(row.get("structured"), dict) and isinstance(row.get("summary"), str) and bool(row.get("summary", "").strip()),
        "product_spine_ready": not product_issues,
        "product_spine_issues": product_issues,
    }


def validate_rows_of_objects(structured: dict[str, Any], key: str, required_field: str | None) -> list[str]:
    if key not in structured:
        return []
    rows = structured.get(key)
    if rows is None:
        return [f"{key} is null; product spine treats it as empty"]
    if not isinstance(rows, list):
        return [f"{key} is not a list"]
    issues = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f"{key}[{index}] is not an object")
            continue
        if required_field is not None:
            value = row.get(required_field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"{key}[{index}] row missing {required_field}")
    return issues


def is_product_spine_compatible(issue: str) -> bool:
    if issue.endswith("is null; product spine treats it as empty"):
        return True
    return False


if __name__ == "__main__":
    main()
