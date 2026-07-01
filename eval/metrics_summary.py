from __future__ import annotations

import re


NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
PUNCTUATION = set(" \t\r\n,.;:!?，。；：！？、（）()[]【】{}<>《》|/-_")


def get_summary_scores(gold_items: list[dict], pred_items: dict[str, dict]) -> dict:
    expected_total = 0
    covered_total = 0
    relaxed_covered_total = 0
    forbidden_total = 0
    unsupported_hits = 0
    missing_summary_count = 0

    for item in gold_items:
        item_id = item["id"]
        pred = pred_items[item_id]
        summary = normalize(pred.get("summary", ""))
        if not summary:
            if pred.get("parse_error"):
                missing_summary_count += 1
            else:
                raise ValueError(f"Prediction missing summary: {item_id}")

        points = item["expected"].get("summary_points", [])
        forbidden = item["expected"].get("forbidden_summary_claims", [])
        expected_total += len(points)
        forbidden_total += len(forbidden)

        for point in points:
            normalized_point = normalize(point)
            if normalized_point in summary:
                covered_total += 1
                relaxed_covered_total += 1
            elif has_relaxed_point_coverage(normalized_point, summary):
                relaxed_covered_total += 1

        for claim in forbidden:
            if has_unsupported_claim(summary, normalize(claim)):
                unsupported_hits += 1

    coverage = covered_total / expected_total if expected_total else 0.0
    relaxed_coverage = relaxed_covered_total / expected_total if expected_total else 0.0
    unsupported_rate = unsupported_hits / forbidden_total if forbidden_total else 0.0
    return {
        "summary_point_coverage": round(coverage, 4),
        "summary_points_covered": covered_total,
        "summary_points_total": expected_total,
        "summary_point_relaxed_coverage": round(relaxed_coverage, 4),
        "summary_points_relaxed_covered": relaxed_covered_total,
        "unsupported_claim_rate": round(unsupported_rate, 4),
        "unsupported_claim_hits": unsupported_hits,
        "forbidden_claim_count": forbidden_total,
        "summary_missing_count": missing_summary_count,
    }


def normalize(text: object) -> str:
    return " ".join(str(text).strip().lower().split())


def has_relaxed_point_coverage(point: str, summary: str) -> bool:
    point_units = content_units(point)
    if len(point_units) < 4:
        return False

    point_numbers = NUMBER_PATTERN.findall(point)
    summary_numbers = NUMBER_PATTERN.findall(summary)
    if point_numbers and not all(number in summary_numbers for number in point_numbers):
        return False

    summary_units = content_units(summary)
    overlap = len(point_units & summary_units)
    return overlap / len(point_units) >= 0.65


def content_units(text: str) -> set[str]:
    return {char for char in text if char not in PUNCTUATION}


def has_unsupported_claim(summary: str, claim: str) -> bool:
    start = summary.find(claim)
    if start < 0:
        return False

    guard = summary[max(0, start - 20) : start]
    negations = (
        "不需要",
        "不要",
        "无需",
        "没有",
        "不能",
        "不可",
        "不应",
        "不能直接",
        "拒绝",
        "避免",
    )
    return not any(word in guard for word in negations)
