from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from train.run_baseline import ModelOutputParseError, normalize_prediction, parse_json


def main() -> None:
    args = parse_args()
    rows = read_jsonl(args.raw_outputs)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    recovered = []
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            item_id = require_id(row)
            raw_output = row.get("raw_output")
            if not isinstance(raw_output, str) or not raw_output.strip():
                prediction = make_parse_error_prediction(item_id, "missing raw_output")
            else:
                try:
                    data = parse_json(raw_output)
                except (json.JSONDecodeError, ValueError, ModelOutputParseError) as exc:
                    prediction = make_parse_error_prediction(item_id, str(exc))
                else:
                    data["id"] = item_id
                    prediction = normalize_prediction(data)
            recovered.append(prediction)
            handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")

    report = build_report(recovered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover prediction JSONL from saved raw model outputs using the runner's parser."
    )
    parser.add_argument("--raw-outputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSONL file: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Bad JSON in {path}:{line_no}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Raw output row must be an object at {path}:{line_no}")
        rows.append(row)
    if not rows:
        raise ValueError(f"Raw output file is empty: {path}")
    return rows


def require_id(row: dict[str, Any]) -> str:
    item_id = row.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError(f"Raw output row missing id: {row}")
    return item_id


def make_parse_error_prediction(item_id: str, message: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "structured": {},
        "summary": "",
        "safety": {"refused": False, "escalated": False},
        "parse_error": message,
    }


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "prediction_count": len(rows),
        "parse_error_count": sum(bool(row.get("parse_error")) for row in rows),
        "json_repair_applied_count": sum(bool(row.get("json_repair_applied")) for row in rows),
        "parse_error_ids": [row["id"] for row in rows if row.get("parse_error")],
        "json_repair_applied_ids": [row["id"] for row in rows if row.get("json_repair_applied")],
    }


if __name__ == "__main__":
    main()
