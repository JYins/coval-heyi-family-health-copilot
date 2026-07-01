from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from src.prediction_normalization import normalize_for_product_spine, summarize_reports
except ModuleNotFoundError:
    from prediction_normalization import normalize_for_product_spine, summarize_reports


@dataclass
class SpineResult:
    database_path: Path
    report_path: Path
    markdown_path: Path | None
    example_count: int
    report_count: int
    lab_item_count: int
    medication_count: int
    symptom_count: int
    appointment_count: int
    safety_event_count: int
    escalation_count: int
    refusal_count: int
    normalization_changed_count: int


def main() -> None:
    args = parse_args()
    result = run_spine(
        gold_path=args.gold,
        prediction_path=args.pred,
        database_path=args.database,
        report_path=args.out,
        markdown_path=args.markdown_out,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "database_path": str(result.database_path),
                "report_path": str(result.report_path),
                "markdown_path": str(result.markdown_path) if result.markdown_path else None,
                "example_count": result.example_count,
                "report_count": result.report_count,
                "lab_item_count": result.lab_item_count,
                "medication_count": result.medication_count,
                "symptom_count": result.symptom_count,
                "appointment_count": result.appointment_count,
                "safety_event_count": result.safety_event_count,
                "escalation_count": result.escalation_count,
                "refusal_count": result.refusal_count,
                "normalization_changed_count": result.normalization_changed_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a fake-data local product spine smoke test."
    )
    parser.add_argument("--gold", type=Path, default=Path("eval/gold/synthetic_v0.jsonl"))
    parser.add_argument(
        "--pred", type=Path, default=Path("eval/gold/fixture_predictions_v0.jsonl")
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("results/product_spine/synthetic_v0.sqlite"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("results/product_spine/synthetic_v0_report.json"),
    )
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def run_spine(
    gold_path: Path,
    prediction_path: Path,
    database_path: Path,
    report_path: Path,
    markdown_path: Path | None,
    limit: int,
) -> SpineResult:
    gold_items = read_jsonl(gold_path)
    normalized_prediction_rows, normalization_report = normalize_prediction_rows(read_jsonl(prediction_path))
    predictions = index_predictions(normalized_prediction_rows)
    selected = gold_items[:limit]
    if not selected:
        raise ValueError("No examples selected for product spine smoke test")

    for item in selected:
        if item["id"] not in predictions:
            raise ValueError(f"Missing prediction for selected example: {item['id']}")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temp_database_path = database_path.with_name(f"{database_path.name}.tmp")
    if temp_database_path.exists():
        temp_database_path.unlink()

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(temp_database_path)
        conn.execute("PRAGMA foreign_keys = ON")
        create_schema(conn)
        for item in selected:
            ingest_example(conn, item, predictions[item["id"]])
        report = build_product_report(conn, normalization_report)
        conn.commit()
        conn.close()
        conn = None
        temp_database_path.replace(database_path)
    finally:
        if conn is not None:
            conn.close()
        if temp_database_path.exists():
            temp_database_path.unlink()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if markdown_path:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(report), encoding="utf-8")

    return SpineResult(
        database_path=database_path,
        report_path=report_path,
        markdown_path=markdown_path,
        example_count=len(selected),
        report_count=count_rows(database_path, "reports"),
        lab_item_count=count_rows(database_path, "lab_items"),
        medication_count=count_rows(database_path, "medications"),
        symptom_count=count_rows(database_path, "symptom_logs"),
        appointment_count=count_rows(database_path, "appointments"),
        safety_event_count=count_rows(database_path, "safety_events"),
        escalation_count=count_filtered(database_path, "safety_events", "escalated = 1"),
        refusal_count=count_filtered(database_path, "safety_events", "refused = 1"),
        normalization_changed_count=normalization_report.get("changed_prediction_count", 0),
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    rows: list[dict[str, Any]] = []
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


def index_predictions(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("id")
        if not item_id:
            raise KeyError("Prediction row missing id")
        if item_id in indexed:
            raise ValueError(f"Duplicate prediction id: {item_id}")
        indexed[item_id] = row
    return indexed


def normalize_prediction_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for row in rows:
        normalized, row_reports = normalize_for_product_spine(row)
        normalized_rows.append(normalized)
        reports.extend(row_reports)
    return normalized_rows, summarize_reports(reports)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY,
            example_id TEXT NOT NULL UNIQUE,
            input_type TEXT NOT NULL,
            report_date TEXT,
            hospital TEXT,
            report_type TEXT,
            input_text TEXT NOT NULL,
            structured_json TEXT NOT NULL,
            summary TEXT NOT NULL
        );

        CREATE TABLE lab_items (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value REAL,
            unit TEXT
        );

        CREATE TABLE medications (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            dose TEXT
        );

        CREATE TABLE symptom_logs (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            symptom_text TEXT NOT NULL,
            onset TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            appointment_date TEXT,
            appointment_type TEXT
        );

        CREATE TABLE safety_events (
            id INTEGER PRIMARY KEY,
            report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            refused INTEGER NOT NULL,
            escalated INTEGER NOT NULL,
            unsafe_request_type TEXT
        );
        """
    )


def ingest_example(conn: sqlite3.Connection, gold: dict[str, Any], pred: dict[str, Any]) -> None:
    structured = pred.get("structured")
    if not isinstance(structured, dict):
        raise ValueError(f"Prediction missing structured object: {pred.get('id')}")

    expected_safety = gold.get("expected", {}).get("safety", {})
    pred_safety = pred.get("safety", {})
    report_id = insert_report(conn, gold, pred, structured)
    insert_lab_items(conn, report_id, list_rows(structured, "lab_items"))
    insert_medications(conn, report_id, list_rows(structured, "medications"))
    insert_symptoms(conn, report_id, list_rows(structured, "symptoms"))
    insert_appointments(conn, report_id, list_rows(structured, "appointments"))
    insert_safety_event(conn, report_id, pred_safety, expected_safety)


def insert_report(
    conn: sqlite3.Connection,
    gold: dict[str, Any],
    pred: dict[str, Any],
    structured: dict[str, Any],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO reports (
            example_id, input_type, report_date, hospital, report_type,
            input_text, structured_json, summary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gold["id"],
            gold.get("input_type") or "unknown",
            structured.get("report_date"),
            structured.get("hospital"),
            structured.get("report_type"),
            gold.get("input_text") or "",
            json.dumps(structured, ensure_ascii=False),
            pred.get("summary") or "",
        ),
    )
    return int(cursor.lastrowid)


def insert_lab_items(conn: sqlite3.Connection, report_id: int, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        name = require_text(row, "name", "lab item")
        conn.execute(
            "INSERT INTO lab_items (report_id, name, value, unit) VALUES (?, ?, ?, ?)",
            (report_id, name, row.get("value"), row.get("unit")),
        )


def insert_medications(conn: sqlite3.Connection, report_id: int, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        name = require_text(row, "name", "medication")
        conn.execute(
            "INSERT INTO medications (report_id, name, dose) VALUES (?, ?, ?)",
            (report_id, name, row.get("dose")),
        )


def insert_symptoms(conn: sqlite3.Connection, report_id: int, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        text = require_text(row, "text", "symptom")
        conn.execute(
            "INSERT INTO symptom_logs (report_id, symptom_text, onset) VALUES (?, ?, ?)",
            (report_id, text, row.get("onset")),
        )


def insert_appointments(conn: sqlite3.Connection, report_id: int, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        conn.execute(
            """
            INSERT INTO appointments (report_id, appointment_date, appointment_type)
            VALUES (?, ?, ?)
            """,
            (report_id, row.get("date"), row.get("type")),
        )


def insert_safety_event(
    conn: sqlite3.Connection,
    report_id: int,
    pred_safety: dict[str, Any],
    expected_safety: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO safety_events (report_id, refused, escalated, unsafe_request_type)
        VALUES (?, ?, ?, ?)
        """,
        (
            report_id,
            int(bool(pred_safety.get("refused"))),
            int(bool(pred_safety.get("escalated"))),
            expected_safety.get("unsafe_request_type"),
        ),
    )


def require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} row missing text field {field!r}: {row}")
    return value


def list_rows(structured: dict[str, Any], field: str) -> list[dict[str, Any]]:
    rows = structured.get(field, [])
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise ValueError(f"structured field {field!r} must be a list or null, got: {rows!r}")
    return rows


def build_product_report(conn: sqlite3.Connection, normalization_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeline": fetch_timeline(conn),
        "doctor_summary": build_doctor_summary(conn),
        "safety_escalations": fetch_safety_events(conn, escalated=True),
        "safety_refusals": fetch_safety_events(conn, refused=True),
        "normalization": normalization_report,
    }


def fetch_timeline(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT example_id, input_type, report_date, hospital, report_type, summary
        FROM reports
        ORDER BY COALESCE(report_date, '9999-99-99'), example_id
        """
    ).fetchall()
    return [
        {
            "example_id": row[0],
            "input_type": row[1],
            "date": row[2],
            "hospital": row[3],
            "report_type": row[4],
            "summary": row[5],
        }
        for row in rows
    ]


def build_doctor_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    recent_reports = conn.execute(
        """
        SELECT example_id, report_date, report_type, summary
        FROM reports
        ORDER BY COALESCE(report_date, '9999-99-99'), example_id
        """
    ).fetchall()
    labs = conn.execute(
        """
        SELECT reports.example_id, lab_items.name, lab_items.value, lab_items.unit
        FROM lab_items
        JOIN reports ON reports.id = lab_items.report_id
        ORDER BY reports.example_id, lab_items.id
        """
    ).fetchall()
    medications = conn.execute(
        """
        SELECT reports.example_id, medications.name, medications.dose
        FROM medications
        JOIN reports ON reports.id = medications.report_id
        ORDER BY reports.example_id, medications.id
        """
    ).fetchall()
    symptoms = conn.execute(
        """
        SELECT reports.example_id, symptom_logs.symptom_text, symptom_logs.onset
        FROM symptom_logs
        JOIN reports ON reports.id = symptom_logs.report_id
        ORDER BY reports.example_id, symptom_logs.id
        """
    ).fetchall()
    return {
        "purpose": "doctor-facing organization summary; not diagnosis or treatment advice",
        "recent_reports": [
            {
                "example_id": row[0],
                "date": row[1],
                "report_type": row[2],
                "summary": row[3],
            }
            for row in recent_reports
        ],
        "lab_items": [
            {
                "example_id": row[0],
                "name": row[1],
                "value": row[2],
                "unit": row[3],
            }
            for row in labs
        ],
        "medications": [
            {
                "example_id": row[0],
                "name": row[1],
                "dose": row[2],
            }
            for row in medications
        ],
        "symptoms": [
            {
                "example_id": row[0],
                "text": row[1],
                "onset": row[2],
            }
            for row in symptoms
        ],
    }


def fetch_safety_events(
    conn: sqlite3.Connection,
    escalated: bool = False,
    refused: bool = False,
) -> list[dict[str, Any]]:
    if escalated == refused:
        raise ValueError("Choose exactly one safety event filter")
    where = "safety_events.escalated = 1" if escalated else "safety_events.refused = 1"
    rows = conn.execute(
        f"""
        SELECT reports.example_id, safety_events.unsafe_request_type, reports.summary
        FROM safety_events
        JOIN reports ON reports.id = safety_events.report_id
        WHERE {where}
        ORDER BY reports.example_id
        """
    ).fetchall()
    return [
        {
            "example_id": row[0],
            "unsafe_request_type": row[1],
            "summary": row[2],
        }
        for row in rows
    ]


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Doctor-Facing Organization Summary",
        "",
        "Purpose: organize synthetic health records for a clinician visit. This is not diagnosis or treatment advice.",
        "",
        "## Timeline",
    ]
    for row in report["timeline"]:
        date = row.get("date") or "date missing"
        label = row.get("report_type") or row.get("input_type") or "record"
        hospital = row.get("hospital") or "hospital missing"
        lines.append(f"- {date} | {label} | {hospital} | {row['summary']}")

    summary = report["doctor_summary"]
    lines.extend(["", "## Lab Items"])
    if summary["lab_items"]:
        for row in summary["lab_items"]:
            value = row["value"] if row["value"] is not None else "value missing"
            unit = row["unit"] or ""
            lines.append(f"- {row['example_id']}: {row['name']} {value} {unit}".rstrip())
    else:
        lines.append("- None recorded in this synthetic run.")

    lines.extend(["", "## Medications"])
    if summary["medications"]:
        for row in summary["medications"]:
            dose = row["dose"] or "dose missing"
            lines.append(f"- {row['example_id']}: {row['name']} ({dose})")
    else:
        lines.append("- None recorded in this synthetic run.")

    lines.extend(["", "## Symptoms"])
    if summary["symptoms"]:
        for row in summary["symptoms"]:
            onset = row["onset"] or "onset missing"
            lines.append(f"- {row['example_id']}: {row['text']} ({onset})")
    else:
        lines.append("- None recorded in this synthetic run.")

    lines.extend(["", "## Safety Escalations"])
    append_safety_rows(lines, report["safety_escalations"])
    lines.extend(["", "## Safety Refusals"])
    append_safety_rows(lines, report["safety_refusals"])
    lines.append("")
    return "\n".join(lines)


def append_safety_rows(lines: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        lines.append("- None recorded in this synthetic run.")
        return
    for row in rows:
        unsafe_type = row["unsafe_request_type"] or "unspecified"
        lines.append(f"- {row['example_id']} ({unsafe_type}): {row['summary']}")


def count_rows(database_path: Path, table: str) -> int:
    with sqlite3.connect(database_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def count_filtered(database_path: Path, table: str, where: str) -> int:
    with sqlite3.connect(database_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])


if __name__ == "__main__":
    main()
