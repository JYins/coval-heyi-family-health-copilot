from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.inference import build_provider_from_env, outbound_network_guard
from src.serve.api_schemas import StructuringRequest


DEFAULT_GOLD = [
    Path("eval/gold/synthetic_v0.jsonl"),
    Path("eval/gold/medication_contrast_v0.jsonl"),
    Path("eval/gold/safety_onset_edge_v1_1.jsonl"),
]


def main() -> None:
    args = parse_args()
    wall_started = time.perf_counter()
    provider = build_provider_from_env()
    descriptor_before = provider.describe()
    if descriptor_before.provider == "mock" and not args.allow_mock:
        raise RuntimeError("Refusing model benchmark with mock provider; pass --allow-mock explicitly")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    dataset_reports: list[dict[str, Any]] = []
    all_latencies: list[float] = []
    all_attempts: list[int] = []
    all_traces: list[dict[str, Any]] = []

    with outbound_network_guard(allow_loopback=True):
        cold_load_ms = provider.start()
        for gold_path in args.gold:
            report = run_dataset(
                provider,
                gold_path,
                args.out_dir,
                prompt_context=args.prompt_context,
            )
            dataset_reports.append(report)
            all_latencies.extend(report["latencies_ms"])
            all_attempts.extend(report["attempts"])
            all_traces.extend(report.pop("traces"))

    descriptor_after = provider.describe()
    summary = {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider_before": descriptor_before.public_dict(),
        "provider_after": descriptor_after.public_dict(),
        "offline_simulation": {
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
            "python_socket_guard": "non_loopback_blocked",
            "physical_network_disconnected": False,
        },
        "hardware": hardware_report(),
        "artifacts": artifact_report(),
        "source_identity": source_identity(),
        "prompt_context": args.prompt_context,
        "generation_config": {
            "max_new_tokens": getattr(provider, "max_new_tokens", None),
            "do_sample": False,
            "repair_attempt_limit": 2,
        },
        "datasets": dataset_reports,
        "cold_load_ms": round(cold_load_ms, 3),
        "latency_ms": latency_summary(all_latencies),
        "warm_latency_ms": latency_summary(all_latencies),
        "generation_metrics": generation_summary(all_traces),
        "repair": {
            "example_count": len(all_attempts),
            "repaired_count": sum(attempt > 1 for attempt in all_attempts),
            "max_attempts_observed": max(all_attempts, default=0),
        },
        "benchmark_wall_ms": round((time.perf_counter() - wall_started) * 1000, 3),
    }
    out_path = args.out_dir / "benchmark_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the configured local structuring provider on fixed synthetic gold sets."
    )
    parser.add_argument("--gold", type=Path, nargs="+", default=DEFAULT_GOLD)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("results/phase2_local_inference/current"),
    )
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument(
        "--prompt-context",
        choices=("semantic", "product"),
        default="semantic",
        help="product omits eval ids and gold input types from model messages",
    )
    return parser.parse_args()


def run_dataset(
    provider: Any,
    gold_path: Path,
    out_root: Path,
    *,
    prompt_context: str,
) -> dict[str, Any]:
    rows = read_jsonl(gold_path)
    dataset_dir = out_root / gold_path.stem
    dataset_dir.mkdir(parents=True, exist_ok=True)
    predictions: list[dict[str, Any]] = []
    latencies: list[float] = []
    attempts: list[int] = []
    traces: list[dict[str, Any]] = []
    for row in rows:
        payload = StructuringRequest(
            member_id="synthetic_benchmark",
            text=row["input_text"],
            input_mode="text",
        )
        if prompt_context == "product":
            result = provider.structure(payload)
            if result.trace.get("prompt_item_id") != "local_request":
                raise RuntimeError("Product-context benchmark leaked a non-default prompt item id")
            if result.trace.get("prompt_input_type") != "text":
                raise RuntimeError("Product-context benchmark leaked a non-text input type")
        else:
            result = provider.structure(
                payload,
                item_id=row["id"],
                input_type=str(row.get("input_type") or "text"),
            )
        prediction = dict(result.prediction)
        prediction["id"] = row["id"]
        predictions.append(prediction)
        latencies.append(result.latency_ms)
        attempts.append(result.attempts)
        traces.append({"id": row["id"], **result.trace})

    prediction_path = dataset_dir / "predictions.jsonl"
    prediction_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
    )
    trace_path = dataset_dir / "traces.jsonl"
    trace_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in traces),
        encoding="utf-8",
    )
    metrics_path = dataset_dir / "metrics.json"
    details_path = dataset_dir / "example_details.json"
    full_contract_gold = all(isinstance(row.get("expected", {}).get("structured"), dict) for row in rows)
    if full_contract_gold:
        subprocess.run(
            [
                sys.executable,
                "eval/run_eval.py",
                "--gold",
                str(gold_path),
                "--pred",
                str(prediction_path),
                "--out",
                str(metrics_path),
                "--details-out",
                str(details_path),
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                sys.executable,
                "eval/run_safety_intent_eval.py",
                "--gold",
                str(gold_path),
                "--pred",
                str(prediction_path),
                "--out",
                str(metrics_path),
            ],
            check=True,
        )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "gold_path": str(gold_path),
        "gold_sha256": sha256_file(gold_path),
        "example_count": len(rows),
        "prediction_path": str(prediction_path),
        "prediction_sha256": sha256_file(prediction_path),
        "trace_path": str(trace_path),
        "trace_sha256": sha256_file(trace_path),
        "metrics_path": str(metrics_path),
        "metrics": metrics,
        "latencies_ms": [round(value, 3) for value in latencies],
        "latency_ms": latency_summary(latencies),
        "attempts": attempts,
        "traces": traces,
        "generation_metrics": generation_summary(traces),
        "prompt_context": prompt_context,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Bad JSON at {path}:{line_no}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_no}")
            rows.append(value)
    if not rows:
        raise ValueError(f"Gold file is empty: {path}")
    return rows


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "max": None, "mean": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "min": round(ordered[0], 3),
        "p50": round(percentile(ordered, 0.50), 3),
        "p95": round(percentile(ordered, 0.95), 3),
        "max": round(ordered[-1], 3),
        "mean": round(statistics.fmean(ordered), 3),
    }


def generation_summary(traces: list[dict[str, Any]]) -> dict[str, Any]:
    generation_ms = [
        float(row["generation_ms"])
        for row in traces
        if isinstance(row.get("generation_ms"), (int, float))
    ]
    input_tokens = [
        int(row["input_tokens"])
        for row in traces
        if isinstance(row.get("input_tokens"), int)
    ]
    output_tokens = [
        int(row["output_tokens"])
        for row in traces
        if isinstance(row.get("output_tokens"), int)
    ]
    total_generation_seconds = sum(generation_ms) / 1000
    return {
        "ttft_ms": "not measured by the in-process provider",
        "generation_latency_ms": latency_summary(generation_ms),
        "input_tokens_total": sum(input_tokens) if input_tokens else None,
        "output_tokens_total": sum(output_tokens) if output_tokens else None,
        "tokens_per_second_weighted": round(sum(output_tokens) / total_generation_seconds, 4)
        if output_tokens and total_generation_seconds > 0
        else None,
        "postprocess_latency_ms": latency_summary(
            [
                float(row["postprocess_ms"])
                for row in traces
                if isinstance(row.get("postprocess_ms"), (int, float))
            ]
        ),
    }


def percentile(ordered: list[float], quantile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def hardware_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "python": sys.version,
    }
    try:
        import torch
    except ImportError:
        report["torch"] = "not_installed"
        return report
    report.update(
        {
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
        }
    )
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        report.update(
            {
                "gpu": properties.name,
                "gpu_total_bytes": properties.total_memory,
                "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(),
            }
        )
    return report


def artifact_report() -> dict[str, Any]:
    base_path = Path(os.environ.get("COVAL_MODEL_BASE_PATH", ""))
    paths = {"base_config": base_path / "config.json"}
    adapter_value = os.environ.get("COVAL_MODEL_ADAPTER_PATH", "").strip()
    if adapter_value:
        adapter_path = Path(adapter_value)
        paths.update(
            {
                "adapter_weights": adapter_path / "adapter_model.safetensors",
                "adapter_config": adapter_path / "adapter_config.json",
            }
        )
    result: dict[str, Any] = {}
    for label, path in paths.items():
        result[label] = (
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            if path.is_file()
            else {"path": str(path), "status": "missing"}
        )
    return result


def source_identity() -> dict[str, Any]:
    source_paths = [
        Path("src/inference/providers.py"),
        Path("src/serve/demo_structuring.py"),
        Path("scripts/benchmark_local_provider.py"),
        Path("train/run_baseline.py"),
        Path("src/prediction_normalization.py"),
        Path("scripts/template_doctor_summary.py"),
        Path("eval/run_eval.py"),
        Path("eval/run_safety_intent_eval.py"),
    ]
    result: dict[str, Any] = {
        "files": {str(path): sha256_file(path) for path in source_paths},
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    result["git_head"] = commit.stdout.strip() if commit.returncode == 0 else "unavailable"
    result["worktree_note"] = "source file hashes are authoritative for this uncommitted run"
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
