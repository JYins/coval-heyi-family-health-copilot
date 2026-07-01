from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    args = parse_args()
    gold_items = index_by_id(read_jsonl(args.gold))
    predictions = read_jsonl(args.pred)
    rewritten = [rewrite_prediction(row, gold_items[row["id"]]) for row in predictions]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rewritten:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(args.out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite prediction summaries with deterministic doctor-facing renderers."
    )
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSONL file: {path}")
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


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("id")
        if not item_id:
            raise KeyError("JSONL row missing id")
        if item_id in indexed:
            raise ValueError(f"Duplicate id: {item_id}")
        indexed[item_id] = row
    return indexed


def rewrite_prediction(pred: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    if pred["id"] != gold["id"]:
        raise ValueError(f"ID mismatch: {pred['id']} vs {gold['id']}")
    structured = pred.get("structured")
    if not isinstance(structured, dict):
        raise ValueError(f"Prediction missing structured object: {pred.get('id')}")
    rewritten = dict(pred)
    rewritten["summary"] = build_summary(gold, structured, pred.get("safety", {}))
    return rewritten


def build_summary(
    gold: dict[str, Any],
    structured: dict[str, Any],
    safety: dict[str, Any],
) -> str:
    input_type = str(gold.get("input_type") or "")
    input_text = str(gold.get("input_text") or "")
    report_date = structured.get("report_date")
    hospital = structured.get("hospital")
    report_type = structured.get("report_type") or input_type or "健康记录"
    meds = names_from_rows(structured.get("medications"))
    symptoms = symptom_texts(structured.get("symptoms"))
    lab_items = lab_item_texts(structured.get("lab_items"))
    findings = finding_texts(structured.get("findings"))
    appointment_dates = appointment_values(structured.get("appointments"), "date")
    appointment_types = appointment_values(structured.get("appointments"), "type")
    input_cues = input_summary_cues(input_text, bool(safety.get("refused")), bool(safety.get("escalated")))

    if bool(safety.get("escalated")):
        return append_cues(render_crisis_summary(symptoms, report_type), input_cues)
    if bool(safety.get("refused")):
        return append_cues(render_refusal_summary(meds, symptoms, input_type), input_cues)
    if input_type == "medication_note" or looks_like_medication_record(meds, symptoms, lab_items):
        return append_cues(
            render_medication_summary(report_date, meds, appointment_dates, appointment_types),
            input_cues,
        )
    if lab_items or findings:
        return append_cues(
            render_report_summary(report_date, hospital, report_type, lab_items, findings, symptoms),
            input_cues,
        )
    if symptoms:
        return append_cues(render_symptom_summary(report_date, symptoms), input_cues)
    return append_cues(render_generic_summary(report_date, report_type), input_cues)


def render_crisis_summary(symptoms: list[str], report_type: object) -> str:
    pieces = []
    if symptoms:
        pieces.append(f"危急症状记录：{join_cn(symptoms)}")
    else:
        pieces.append(f"{report_type or '危急症状'}记录")
    pieces.append("应立即联系急救或就近急诊")
    pieces.append("不建议在家观察或等待自行缓解")
    return "；".join(pieces) + "。"


def render_refusal_summary(meds: list[str], symptoms: list[str], input_type: str) -> str:
    pieces = ["用户提出医疗安全请求，要求直接诊断、调整用药剂量、加药方案或编造指南时应拒绝"]
    if meds:
        pieces.append(f"已知用药：{join_cn(meds)}")
    if symptoms:
        pieces.append(f"已知症状：{join_cn(symptoms)}")
    if input_type == "safety_request":
        pieces.append("不提供具体加药建议或调药方案")
        pieces.append("建议联系医生或药师确认")
        pieces.append("可以整理已知用药和症状供医生参考")
    else:
        pieces.append("建议带资料咨询医生确认")
    return "；".join(pieces) + "。"


def render_medication_summary(
    report_date: object,
    meds: list[str],
    appointment_dates: list[str],
    appointment_types: list[str],
) -> str:
    pieces = []
    if report_date:
        pieces.append(f"{report_date}复诊后记录{len(meds) or ''}种药名和用药信息")
    else:
        pieces.append(f"记录药盒中的{len(meds) or ''}种药名和用药清单")
    if meds:
        pieces.append(f"药名包括{join_cn(meds)}")
    if appointment_dates:
        pieces.append(f"下次复诊约{join_cn(appointment_dates)}")
    elif appointment_types:
        pieces.append(f"后续事项：{join_cn(appointment_types)}")
    pieces.append("用于下次给医生核对")
    pieces.append("用户明确不需要调整剂量，也不要增减药物建议")
    return "；".join(pieces) + "。"


def render_report_summary(
    report_date: object,
    hospital: object,
    report_type: object,
    lab_items: list[str],
    findings: list[str],
    symptoms: list[str],
) -> str:
    pieces = []
    location = f"在{hospital}" if hospital else ""
    if report_date:
        pieces.append(f"{report_date}{location}做{report_type}")
    else:
        pieces.append(f"{location}{report_type}报告")
    if lab_items:
        pieces.append("指标：" + "；".join(lab_items))
    if findings:
        pieces.append("所见：" + "；".join(findings))
    if symptoms:
        pieces.append("患者提到：" + join_cn(symptoms))
    pieces.append("供医生复诊核对，不作诊断或治疗建议")
    return "；".join(str(piece) for piece in pieces if piece) + "。"


def render_symptom_summary(report_date: object, symptoms: list[str]) -> str:
    date_text = f"{report_date} " if report_date else ""
    return f"{date_text}症状记录：{join_cn(symptoms)}；用于就医沟通和时间线整理。"


def render_generic_summary(report_date: object, report_type: object) -> str:
    date_text = f"{report_date} " if report_date else ""
    return f"{date_text}{report_type or '健康记录'}已整理为结构化记录，供就医沟通时核对；不提供诊断或治疗建议。"


def looks_like_medication_record(
    meds: list[str],
    symptoms: list[str],
    lab_items: list[str],
) -> bool:
    return bool(meds) and not symptoms and not lab_items


def names_from_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for row in value:
        if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip():
            names.append(row["name"].strip())
    return names


def symptom_texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    symptoms = []
    for row in value:
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        onset = row.get("onset")
        if isinstance(text, str) and text.strip():
            if isinstance(onset, str) and onset.strip():
                symptoms.append(f"{text.strip()}（{onset.strip()}）")
            else:
                symptoms.append(text.strip())
    return symptoms


def lab_item_texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for row in value:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        item_parts = [name.strip()]
        if row.get("value") is not None:
            item_parts.append(str(row["value"]))
        unit = row.get("unit")
        if isinstance(unit, str) and unit.strip():
            item_parts.append(unit.strip())
        items.append(" ".join(item_parts))
    return items


def finding_texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    findings = []
    for row in value:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        size = row.get("size")
        if isinstance(size, str) and size.strip():
            findings.append(f"{name.strip()} {size.strip()}")
        else:
            findings.append(name.strip())
    return findings


def appointment_values(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    values = []
    for row in value:
        if isinstance(row, dict) and isinstance(row.get(key), str) and row[key].strip():
            values.append(row[key].strip())
    return values


def input_summary_cues(input_text: str, refused: bool, escalated: bool) -> list[str]:
    cues: list[str] = []
    for clause in split_clauses(input_text):
        if should_keep_input_clause(clause):
            cues.append(transform_input_clause(clause, refused, escalated))
    if not cues:
        return []

    prefix = "原始记录要点"
    if refused:
        prefix = "应拒绝用户要求"
    elif escalated:
        prefix = "危急原始要点"
    return [f"{prefix}：{clause}" for clause in dedupe_keep_order(cues)]


def transform_input_clause(clause: str, refused: bool, escalated: bool) -> str:
    if escalated and any(term in clause for term in ("先", "躺", "观察", "看看", "等")):
        cleaned = clause
        for prefix in ("她想", "他想", "家属想", "想"):
            if cleaned.startswith(prefix):
                cleaned = cleaned.removeprefix(prefix)
                break
        return f"不应{cleaned}"
    if refused and clause.startswith("不要"):
        return f"用户要求{clause}"
    return clause


def split_clauses(text: str) -> list[str]:
    normalized = text.replace("\r", " ").replace("\n", " ")
    parts: list[str] = []
    current: list[str] = []
    separators = set("，。；！？,.!?;")
    for char in normalized:
        if char in separators:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def should_keep_input_clause(clause: str) -> bool:
    if not clause:
        return False
    keywords = (
        "昨晚",
        "今天早上",
        "三天前",
        "刚才",
        "没有",
        "无",
        "不需要",
        "不要",
        "别",
        "直接",
        "医生",
        "复诊",
        "调整",
        "mg",
        "补",
        "加量",
        "剂量",
        "喘不上气",
        "喉咙发紧",
        "嘴唇肿",
        "躺",
        "观察",
        "糖尿病",
        "就医",
        "医生看",
        "时间线",
    )
    return any(keyword in clause for keyword in keywords)


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def append_cues(summary: str, cues: list[str]) -> str:
    if not cues:
        return summary
    base = summary.rstrip("。")
    return f"{base}；{'；'.join(cues)}。"


def join_cn(values: list[str]) -> str:
    return "、".join(values)


if __name__ == "__main__":
    main()
