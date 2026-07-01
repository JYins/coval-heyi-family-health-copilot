from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.prediction_normalization import normalize_report_type_row, summarize_reports


def main() -> None:
    args = parse_args()
    rows = read_jsonl(args.pred)
    normalized_rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    for row in rows:
        normalized, report = normalize_report_type_row(row)
        normalized_rows.append(normalized)
        reports.append(report)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out, normalized_rows)
    summary = summarize_reports(reports)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    safe_print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize report_type labels without changing extraction rows or safety decisions."
    )
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def safe_print(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace") + "\n")


if __name__ == "__main__":
    main()
