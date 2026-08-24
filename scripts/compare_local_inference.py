from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DATASETS = ("synthetic_v0", "medication_contrast_v0", "safety_onset_edge_v1_1")
DEFAULT_RUNS = {
    "mock": Path("results/phase2_local_inference/mock/benchmark_summary.json"),
    "base_bnb4": Path(
        "results/phase2_local_inference/transformers_base_bnb4/benchmark_summary.json"
    ),
    "adapter_bnb4": Path(
        "results/phase2_local_inference/transformers_adapter_bnb4/benchmark_summary.json"
    ),
}
HISTORICAL_ROOT = Path("results/sft_v2_eval_template_patch")
HISTORICAL_METRICS = "metrics_recovered_report_type_template_summary.json"
MAX_F1_REGRESSION = 0.03


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare local provider quality and latency on the fixed synthetic slices."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("results/phase2_local_inference/comparison"),
    )
    args = parser.parse_args()
    runs = {name: read_json(path) for name, path in DEFAULT_RUNS.items()}
    historical = {
        dataset: read_json(HISTORICAL_ROOT / dataset / HISTORICAL_METRICS)
        for dataset in DATASETS
    }

    rows = []
    for dataset in DATASETS:
        mock = metrics_for(runs["mock"], dataset)
        base = metrics_for(runs["base_bnb4"], dataset)
        adapter = metrics_for(runs["adapter_bnb4"], dataset)
        accepted = historical[dataset]
        historical_delta = round(
            adapter["extraction_field_f1"] - accepted["extraction_field_f1"], 4
        )
        rows.append(
            {
                "dataset": dataset,
                "example_count": adapter["example_count"],
                "mock_f1": mock["extraction_field_f1"],
                "base_bnb4_f1": base["extraction_field_f1"],
                "adapter_bnb4_f1": adapter["extraction_field_f1"],
                "adapter_minus_base_f1": round(
                    adapter["extraction_field_f1"] - base["extraction_field_f1"], 4
                ),
                "historical_accepted_f1": accepted["extraction_field_f1"],
                "adapter_minus_historical_f1": historical_delta,
                "historical_reference_within_0_03": historical_delta >= -MAX_F1_REGRESSION,
                "adapter_relaxed_summary": adapter["summary_point_relaxed_coverage"],
                "historical_relaxed_summary": accepted[
                    "summary_point_relaxed_coverage"
                ],
                "adapter_safety_refusal": adapter["safety_refusal_rate"],
                "base_false_refusal": base["safety_false_refusal_rate"],
                "adapter_false_refusal": adapter["safety_false_refusal_rate"],
                "adapter_crisis_recall": adapter["crisis_escalation_recall"],
            }
        )

    comparison = {
        "schema_version": 1,
        "synthetic_only": True,
        "frozen_local_quantization_gate": {
            "status": "not_evaluable",
            "reason": "no same-local unquantized accepted-provider comparator fits the available 8 GB runtime",
            "maximum_allowed_regression": MAX_F1_REGRESSION,
        },
        "historical_reference_check": {
            "descriptive_only": True,
            "all_slices_within_0_03": all(
                row["historical_reference_within_0_03"] for row in rows
            ),
        },
        "deployment_decision": "blocked",
        "quality": rows,
        "latency_ms": {
            name: {
                "cold_load": summary.get("cold_load_ms"),
                "warm_p50": summary["latency_ms"]["p50"],
                "warm_p95": summary["latency_ms"]["p95"],
                "warm_mean": summary["latency_ms"]["mean"],
            }
            for name, summary in runs.items()
        },
        "historical_latency": "not recorded; no value inferred",
        "source_artifacts": {
            str(path): sha256_file(path)
            for path in [
                *DEFAULT_RUNS.values(),
                *(HISTORICAL_ROOT / dataset / HISTORICAL_METRICS for dataset in DATASETS),
            ]
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "comparison.json"
    markdown_path = args.out_dir / "comparison.md"
    json_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown_report(comparison), encoding="utf-8")
    print(json_path)
    print(markdown_path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def metrics_for(summary: dict[str, Any], dataset: str) -> dict[str, Any]:
    for row in summary["datasets"]:
        if row["metrics"]["dataset_version"] == dataset:
            return row["metrics"]
    raise KeyError(f"Missing dataset {dataset}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def markdown_report(comparison: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 local inference comparison",
        "",
        "All current-run inputs are fixed synthetic/public-safe gold rows. "
        "Historical latency was not recorded and is not estimated.",
        "",
        "| slice | n | mock F1 | base bnb4 F1 | v2 bnb4 F1 | v2-base | historical accepted | v2-historical | historical check | base/v2 false refusal |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in comparison["quality"]:
        lines.append(
            "| {dataset} | {example_count} | {mock_f1:.4f} | {base_bnb4_f1:.4f} | "
            "{adapter_bnb4_f1:.4f} | {adapter_minus_base_f1:+.4f} | "
            "{historical_accepted_f1:.4f} | {adapter_minus_historical_f1:+.4f} | {check} | "
            "{base_false_refusal:.4f}/{adapter_false_refusal:.4f} |".format(
                **row,
                check=(
                    "within 0.03"
                    if row["historical_reference_within_0_03"]
                    else "outside 0.03"
                ),
            )
        )
    lines.extend(
        [
            "",
            "| run | cold load ms | warm p50 ms | warm p95 ms | warm mean ms |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, row in comparison["latency_ms"].items():
        cold = "not measured" if row["cold_load"] is None else f'{row["cold_load"]:.3f}'
        lines.append(
            f'| {name} | {cold} | {row["warm_p50"]:.3f} | '
            f'{row["warm_p95"]:.3f} | {row["warm_mean"]:.3f} |'
        )
    lines.extend(
        [
            "",
            "Frozen same-local quantization gate: **NOT EVALUABLE** (no local unquantized accepted comparator).",
            "Historical comparison is descriptive only; deployment decision: **BLOCKED**.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
