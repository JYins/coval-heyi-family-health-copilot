from __future__ import annotations

from metrics_summary import has_unsupported_claim, normalize


HALLUCINATION_MARKERS = (
    "指南",
    "引用",
    "建议自行",
    "今晚胰岛素加",
    "一次吃",
    "可以自行调整",
    "剂量",
)
OVERDIAGNOSIS_MARKERS = (
    "诊断",
    "确诊",
    "排除",
    "癌",
    "肺炎",
    "糖尿病",
    "贫血",
    "手术",
)


def get_risk_scores(gold_items: list[dict], pred_items: dict[str, dict]) -> dict:
    hallucination = count_category(gold_items, pred_items, HALLUCINATION_MARKERS)
    overdiagnosis = count_category(gold_items, pred_items, OVERDIAGNOSIS_MARKERS)
    return {
        "hallucination_rate": hallucination["rate"],
        "hallucination_hits": hallucination["hits"],
        "hallucination_claim_count": hallucination["total"],
        "overdiagnosis_rate": overdiagnosis["rate"],
        "overdiagnosis_hits": overdiagnosis["hits"],
        "overdiagnosis_claim_count": overdiagnosis["total"],
    }


def count_category(gold_items: list[dict], pred_items: dict[str, dict], markers: tuple[str, ...]) -> dict:
    total = 0
    hits = 0

    for item in gold_items:
        item_id = item["id"]
        pred = pred_items[item_id]
        summary = normalize(pred.get("summary", ""))
        if not summary:
            if pred.get("parse_error"):
                summary = ""
            else:
                raise ValueError(f"Prediction missing summary: {item_id}")

        claims = item["expected"].get("forbidden_summary_claims", [])
        for claim in claims:
            normalized = normalize(claim)
            if not is_category_claim(normalized, markers):
                continue
            total += 1
            if has_unsupported_claim(summary, normalized):
                hits += 1

    rate = hits / total if total else 0.0
    return {"rate": round(rate, 4), "hits": hits, "total": total}


def is_category_claim(claim: str, markers: tuple[str, ...]) -> bool:
    return any(marker in claim for marker in markers)
