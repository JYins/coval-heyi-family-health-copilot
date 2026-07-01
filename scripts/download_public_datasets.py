from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    local_id: str
    hf_id: str
    license: str
    purpose: str
    configs: tuple[str | None, ...] = (None,)
    splits: tuple[str, ...] = ("train",)
    snapshot_only: bool = False


DATASETS = (
    DatasetSpec(
        local_id="medical_o1_reasoning_zh",
        hf_id="FreedomIntelligence/medical-o1-reasoning-SFT",
        configs=("zh", "zh_mix"),
        splits=("train",),
        license="apache-2.0",
        purpose="Candidate public SFT source. Use only after filtering into this project's schema.",
    ),
    DatasetSpec(
        local_id="medmcqa",
        hf_id="openlifescienceai/medmcqa",
        configs=(None,),
        splits=("validation", "test"),
        license="apache-2.0",
        purpose="External medical QA sanity benchmark, not family-health private data.",
    ),
    DatasetSpec(
        local_id="pubmed_qa_snapshot",
        hf_id="bigbio/pubmed_qa",
        configs=(None,),
        splits=(),
        license="needs_review",
        purpose="External QA/RAG benchmark candidate. Snapshot only because the HF loader requires arbitrary Python code review.",
        snapshot_only=True,
    ),
)


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    out_dir = project_root / "data" / "public"
    cache_dir = project_root / "data" / "hf_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for spec in DATASETS:
        if spec.license == "needs_review" and not args.include_needs_review:
            print(f"Skipping {spec.local_id}: license needs review", flush=True)
            rows.append(
                {
                    **asdict(spec),
                    "config": "skipped",
                    "split": "skipped",
                    "rows_available": None,
                    "rows_written": 0,
                    "path": None,
                    "skipped_reason": "license_needs_review",
                }
            )
            continue
        if spec.snapshot_only:
            rows.append(download_snapshot(spec, out_dir, cache_dir))
        else:
            rows.extend(download_dataset_rows(spec, out_dir, cache_dir, args.max_rows))

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "max_rows_per_split": args.max_rows,
        "datasets": rows,
    }
    manifest_path = out_dir / "download_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public candidate datasets for lora_health.")
    parser.add_argument("--project-root", type=Path, default=Path("/home/syin94/scratch/lora_health"))
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
        help="Rows per config/split. Use 0 for full splits.",
    )
    parser.add_argument(
        "--include-needs-review",
        action="store_true",
        help="Also download datasets whose license/loader still needs review.",
    )
    return parser.parse_args()


def download_dataset_rows(
    spec: DatasetSpec,
    out_dir: Path,
    cache_dir: Path,
    max_rows: int,
) -> list[dict[str, Any]]:
    from datasets import load_dataset

    records: list[dict[str, Any]] = []
    for config in spec.configs:
        for split in spec.splits:
            print(
                f"Downloading {spec.local_id} config={config or 'default'} split={split}",
                flush=True,
            )
            dataset = load_dataset(
                spec.hf_id,
                config,
                split=split,
                cache_dir=str(cache_dir),
                trust_remote_code=False,
            )
            limit = len(dataset) if max_rows == 0 else min(max_rows, len(dataset))
            target_dir = out_dir / spec.local_id / (config or "default")
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f"{split}.jsonl"

            with target_path.open("w", encoding="utf-8") as handle:
                for row in dataset.select(range(limit)):
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

            records.append(
                {
                    **asdict(spec),
                    "config": config or "default",
                    "split": split,
                    "rows_available": len(dataset),
                    "rows_written": limit,
                    "path": str(target_path),
                }
            )
            print(f"Wrote {limit} rows to {target_path}", flush=True)
    return records


def download_snapshot(spec: DatasetSpec, out_dir: Path, cache_dir: Path) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    print(f"Downloading snapshot {spec.local_id} from {spec.hf_id}", flush=True)
    target_dir = out_dir / spec.local_id / "snapshot"
    snapshot_path = snapshot_download(
        repo_id=spec.hf_id,
        repo_type="dataset",
        cache_dir=str(cache_dir),
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )
    return {
        **asdict(spec),
        "config": "snapshot",
        "split": "snapshot",
        "rows_available": None,
        "rows_written": None,
        "path": snapshot_path,
    }


if __name__ == "__main__":
    main()
