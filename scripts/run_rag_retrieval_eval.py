from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_K_VALUES = (1, 3)


def main() -> None:
    args = parse_args()
    corpus = read_jsonl(args.corpus)
    gold = read_jsonl(args.gold)
    metrics, details = evaluate_retrieval(
        corpus=corpus,
        gold=gold,
        k_values=tuple(args.k),
        no_answer_threshold=args.no_answer_threshold,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.details_out:
        args.details_out.parent.mkdir(parents=True, exist_ok=True)
        args.details_out.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Phase 6 retrieval-first RAG eval smoke test.")
    parser.add_argument("--corpus", type=Path, default=Path("data/public/rag_v0/corpus.jsonl"))
    parser.add_argument("--gold", type=Path, default=Path("eval/rag/gold_v0.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("results/rag_v0/metrics.json"))
    parser.add_argument("--details-out", type=Path, default=Path("results/rag_v0/details.json"))
    parser.add_argument("--k", type=int, nargs="+", default=list(DEFAULT_K_VALUES))
    parser.add_argument("--no-answer-threshold", type=float, default=0.08)
    return parser.parse_args()


def evaluate_retrieval(
    corpus: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    k_values: tuple[int, ...],
    no_answer_threshold: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not corpus:
        raise ValueError("RAG corpus is empty")
    if not gold:
        raise ValueError("RAG gold set is empty")

    corpus_by_id = index_by_id(corpus, "corpus")
    max_k = max(k_values)
    details = []
    reciprocal_ranks = []
    recall_hits = {k: 0 for k in k_values}
    answerable_count = 0
    no_answer_count = 0
    no_answer_correct = 0

    prepared_docs = [(doc, weighted_terms(document_text(doc))) for doc in corpus]

    for query in gold:
        query_id = require_str(query, "id")
        relevant_ids = set(query.get("relevant_ids", []))
        answerable = bool(query.get("answerable", True))
        if not answerable and relevant_ids:
            raise ValueError(f"No-answer query cannot declare relevant ids: {query_id}")
        for doc_id in relevant_ids:
            if doc_id not in corpus_by_id:
                raise ValueError(f"Gold query {query_id} references missing corpus id: {doc_id}")

        ranked = rank(query["query"], prepared_docs)
        top = ranked[:max_k]
        retrieved_ids = [item["id"] for item in top]
        top_score = top[0]["score"] if top else 0.0
        predicted_no_answer = top_score < no_answer_threshold

        if answerable:
            answerable_count += 1
            rank_position = first_relevant_rank(ranked, relevant_ids)
            reciprocal_ranks.append(0.0 if rank_position is None else 1.0 / rank_position)
            for k in k_values:
                if relevant_ids.intersection(retrieved_ids[:k]):
                    recall_hits[k] += 1
        else:
            no_answer_count += 1
            if predicted_no_answer:
                no_answer_correct += 1

        details.append(
            {
                "id": query_id,
                "query": query["query"],
                "answerable": answerable,
                "relevant_ids": sorted(relevant_ids),
                "predicted_no_answer": predicted_no_answer,
                "top_score": round(top_score, 4),
                "retrieved": [
                    {
                        "id": item["id"],
                        "rank": index + 1,
                        "score": round(item["score"], 4),
                        "title": item["title"],
                    }
                    for index, item in enumerate(top)
                ],
            }
        )

    metrics: dict[str, Any] = {
        "dataset_version": get_dataset_version(gold),
        "corpus_size": len(corpus),
        "query_count": len(gold),
        "answerable_count": answerable_count,
        "no_answer_count": no_answer_count,
        "no_answer_threshold": no_answer_threshold,
        "mrr": round(sum(reciprocal_ranks) / answerable_count, 4) if answerable_count else 0.0,
        "no_answer_accuracy": round(no_answer_correct / no_answer_count, 4) if no_answer_count else None,
    }
    for k in k_values:
        metrics[f"recall_at_{k}"] = round(recall_hits[k] / answerable_count, 4) if answerable_count else 0.0
    return metrics, details


def rank(query: str, prepared_docs: list[tuple[dict[str, Any], Counter[str]]]) -> list[dict[str, Any]]:
    query_terms = weighted_terms(query)
    scored = []
    for doc, doc_terms in prepared_docs:
        score = cosine(query_terms, doc_terms)
        scored.append(
            {
                "id": doc["id"],
                "title": doc.get("title", ""),
                "score": score,
            }
        )
    return sorted(scored, key=lambda item: (-item["score"], item["id"]))


def weighted_terms(text: str) -> Counter[str]:
    normalized = text.lower()
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    latin_tokens = re.findall(r"[a-z0-9]+", normalized)
    terms: Counter[str] = Counter(latin_tokens)
    terms.update(chinese_chars)
    terms.update("".join(pair) for pair in zip(chinese_chars, chinese_chars[1:]))
    terms.update("".join(triple) for triple in zip(chinese_chars, chinese_chars[1:], chinese_chars[2:]))
    return terms


def cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = set(left) & set(right)
    dot = sum(left[key] * right[key] for key in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def document_text(doc: dict[str, Any]) -> str:
    return "\n".join([str(doc.get("title", "")), str(doc.get("source", "")), str(doc.get("text", ""))])


def first_relevant_rank(ranked: list[dict[str, Any]], relevant_ids: set[str]) -> int | None:
    for index, item in enumerate(ranked, start=1):
        if item["id"] in relevant_ids:
            return index
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def index_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    items = {}
    for row in rows:
        item_id = require_str(row, "id")
        if item_id in items:
            raise ValueError(f"Duplicate {label} id: {item_id}")
        items[item_id] = row
    return items


def require_str(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Row missing non-empty string field: {key}")
    return value


def get_dataset_version(rows: list[dict[str, Any]]) -> str:
    versions = {row.get("dataset_version") for row in rows}
    if len(versions) != 1:
        raise ValueError(f"Gold set must contain exactly one dataset_version, got: {versions}")
    version = versions.pop()
    if not version:
        raise ValueError("Gold set missing dataset_version")
    return str(version)


if __name__ == "__main__":
    main()
