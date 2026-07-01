from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TOP_LEVEL = {"id", "structured", "summary", "safety"}
REQUIRED_STRUCTURED = {
    "patient",
    "report_date",
    "hospital",
    "report_type",
    "lab_items",
    "medications",
    "symptoms",
    "appointments",
    "findings",
}
COLLECTION_FIELDS = {"lab_items", "medications", "symptoms", "appointments", "findings"}
SECRET_PATTERNS = [
    re.compile(r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    re.compile(r"(?i)huggingface_token|openai_api_key"),
    re.compile(r"(?i)\b(password|passwd|secret|token)\b\s*[:=]\s*[^,\s]{8,}"),
    re.compile(r"/home/syin94/scratch/MEng_Project"),
    re.compile(r"data/private"),
]


def main() -> None:
    args = parse_args()
    errors: list[str] = []
    train_rows = load_jsonl(args.train_jsonl, errors)
    val_rows = load_jsonl(args.val_jsonl, errors)
    rows = train_rows + val_rows

    errors.extend(check_rows(rows))
    errors.extend(check_split(train_rows, val_rows))
    errors.extend(check_eval_leakage(rows, args.gold))
    errors.extend(check_manifest(args.manifest, len(train_rows), len(val_rows)))

    report = {
        "dataset_version": read_manifest_version(args.manifest),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "checked_rows": len(rows),
        "gold_files_checked": [str(path) for path in args.gold],
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if errors:
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the synthetic SFT smoke dataset.")
    parser.add_argument("--train-jsonl", type=Path, default=Path("data/public/sft_smoke_v0/train.jsonl"))
    parser.add_argument("--val-jsonl", type=Path, default=Path("data/public/sft_smoke_v0/val.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/public/sft_smoke_v0/manifest.json"))
    parser.add_argument(
        "--gold",
        type=Path,
        nargs="*",
        default=[Path("eval/gold/synthetic_v0.jsonl"), Path("eval/gold/medication_contrast_v0.jsonl")],
    )
    parser.add_argument("--report", type=Path, default=Path("results/sft_smoke_validation.json"))
    return parser.parse_args()


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        errors.append(f"missing jsonl: {path}")
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_no} invalid JSON: {exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"{path}:{line_no} row must be an object")
                continue
            rows.append(row)
    return rows


def check_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors = []
    ids: set[str] = set()
    for row in rows:
        row_id = str(row.get("id", ""))
        if not row_id:
            errors.append("training row missing id")
            continue
        if row_id in ids:
            errors.append(f"duplicate training id: {row_id}")
        ids.add(row_id)

        messages = row.get("messages")
        if not isinstance(messages, list) or [m.get("role") for m in messages] != ["system", "user", "assistant"]:
            errors.append(f"{row_id}: messages must be system/user/assistant")
            continue
        for message in messages:
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                errors.append(f"{row_id}: message content is empty")
            errors.extend(check_forbidden_text(row_id, content or ""))

        assistant_text = messages[2].get("content", "")
        try:
            assistant = json.loads(assistant_text)
        except json.JSONDecodeError as exc:
            errors.append(f"{row_id}: assistant content is not JSON: {exc}")
            continue
        errors.extend(check_assistant_output(row_id, assistant))
    return errors


def check_assistant_output(row_id: str, output: Any) -> list[str]:
    errors = []
    if not isinstance(output, dict):
        return [f"{row_id}: assistant JSON must be an object"]
    missing = REQUIRED_TOP_LEVEL - set(output)
    if missing:
        errors.append(f"{row_id}: missing assistant keys {sorted(missing)}")
    if output.get("id") != row_id:
        errors.append(f"{row_id}: assistant id does not match row id")
    structured = output.get("structured")
    if not isinstance(structured, dict):
        errors.append(f"{row_id}: structured must be an object")
        return errors
    missing_structured = REQUIRED_STRUCTURED - set(structured)
    if missing_structured:
        errors.append(f"{row_id}: missing structured keys {sorted(missing_structured)}")
    for field in COLLECTION_FIELDS:
        if field in structured and not isinstance(structured[field], list):
            errors.append(f"{row_id}: structured.{field} must be a list")
    safety = output.get("safety")
    if not isinstance(safety, dict):
        errors.append(f"{row_id}: safety must be an object")
    else:
        for key in ["refused", "escalated"]:
            if not isinstance(safety.get(key), bool):
                errors.append(f"{row_id}: safety.{key} must be boolean")
    if not isinstance(output.get("summary"), str) or not output.get("summary", "").strip():
        errors.append(f"{row_id}: summary must be non-empty")
    return errors


def check_split(train_rows: list[dict[str, Any]], val_rows: list[dict[str, Any]]) -> list[str]:
    errors = []
    if len(train_rows) < 8:
        errors.append(f"train split too small for smoke coverage: {len(train_rows)}")
    if len(val_rows) < 2:
        errors.append(f"validation split too small: {len(val_rows)}")
    train_ids = {row.get("id") for row in train_rows}
    val_ids = {row.get("id") for row in val_rows}
    overlap = train_ids & val_ids
    if overlap:
        errors.append(f"train/val id overlap: {sorted(overlap)}")
    return errors


def check_eval_leakage(rows: list[dict[str, Any]], gold_paths: list[Path]) -> list[str]:
    errors = []
    train_ids = {str(row.get("id")) for row in rows}
    train_texts = {extract_user_text(row) for row in rows}
    train_texts.discard("")
    for path in gold_paths:
        gold_rows = load_jsonl(path, errors)
        for gold in gold_rows:
            gold_id = str(gold.get("id", ""))
            if gold_id in train_ids:
                errors.append(f"training id overlaps eval gold id: {gold_id}")
            gold_text = str(gold.get("input_text", ""))
            if gold_text and gold_text in train_texts:
                errors.append(f"training input exactly duplicates eval gold text: {gold_id}")
    return errors


def extract_user_text(row: dict[str, Any]) -> str:
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return ""
    content = messages[1].get("content", "")
    if not isinstance(content, str):
        return ""
    marker = "输入文本："
    if marker in content:
        return content.split(marker, 1)[1].strip()
    return content.strip()


def check_manifest(manifest_path: Path, train_count: int, val_count: int) -> list[str]:
    if not manifest_path.exists():
        return [f"missing manifest: {manifest_path}"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    if data.get("privacy") != "public/synthetic only; no real family or patient data":
        errors.append("manifest privacy statement changed or missing")
    if data.get("train_rows") != train_count:
        errors.append(f"manifest train_rows mismatch: {data.get('train_rows')} != {train_count}")
    if data.get("val_rows") != val_count:
        errors.append(f"manifest val_rows mismatch: {data.get('val_rows')} != {val_count}")
    if "eval/gold" not in data.get("eval_leakage_policy", ""):
        errors.append("manifest missing eval leakage policy")
    return errors


def read_manifest_version(manifest_path: Path) -> str | None:
    if not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data.get("dataset_version")


def check_forbidden_text(row_id: str, text: str) -> list[str]:
    errors = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{row_id}: forbidden text matched {pattern.pattern!r}")
    return errors


if __name__ == "__main__":
    main()
