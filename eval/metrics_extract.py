from __future__ import annotations

from collections.abc import Iterable


def get_extraction_scores(gold_items: list[dict], pred_items: dict[str, dict]) -> dict:
    gold_pairs: list[tuple[str, str]] = []
    pred_pairs: list[tuple[str, str]] = []

    for item in gold_items:
        item_id = require_id(item)
        pred = require_pred(item_id, pred_items)
        gold_structured = item["expected"]["structured"]
        pred_structured = pred.get("structured")
        if pred_structured is None:
            raise KeyError(f"Prediction missing structured output: {item_id}")

        gold_pairs.extend((item_id, value) for value in flatten_values(gold_structured))
        pred_pairs.extend((item_id, value) for value in flatten_values(pred_structured))

    return get_prf(set(gold_pairs), set(pred_pairs), prefix="extraction_field")


def flatten_values(value: object, path: str = "") -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, dict):
        for key in sorted(value):
            next_path = f"{path}.{key}" if path else key
            yield from flatten_values(value[key], next_path)
        return
    if isinstance(value, list):
        for row in value:
            if isinstance(row, dict):
                label = row.get("name") or row.get("text") or row.get("id")
                row_path = f"{path}[{normalize(label)}]" if label else path
                yield from flatten_values(row, row_path)
            else:
                yield from flatten_values(row, path)
        return
    yield f"{path}={normalize(value)}"


def get_prf(gold: set[tuple[str, str]], pred: set[tuple[str, str]], prefix: str) -> dict:
    true_pos = len(gold & pred)
    precision = true_pos / len(pred) if pred else 0.0
    recall = true_pos / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        f"{prefix}_precision": round(precision, 4),
        f"{prefix}_recall": round(recall, 4),
        f"{prefix}_f1": round(f1, 4),
        f"{prefix}_gold_count": len(gold),
        f"{prefix}_pred_count": len(pred),
    }


def normalize(value: object) -> str:
    text = str(value).strip().lower()
    return " ".join(text.split())


def require_id(item: dict) -> str:
    item_id = item.get("id")
    if not item_id:
        raise KeyError("Gold item missing id")
    return item_id


def require_pred(item_id: str, pred_items: dict[str, dict]) -> dict:
    if item_id not in pred_items:
        raise KeyError(f"Missing prediction for gold item: {item_id}")
    return pred_items[item_id]
