from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import snapshot_download


DEFAULT_MODEL_PATTERNS = (
    "*.json",
    "*.model",
    "*.safetensors",
    "*.txt",
    "tokenizer*",
    "vocab*",
    "merges.txt",
)


def main() -> None:
    args = parse_args()
    model_ids = args.model_id or ["Qwen/Qwen2.5-7B-Instruct"]
    allow_patterns = args.allow_pattern or list(DEFAULT_MODEL_PATTERNS)
    ignore_patterns = args.ignore_pattern or ["*.bin", "*.h5", "*.msgpack"]
    cache_dir = args.cache_dir.resolve()
    manifest_path = args.manifest.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for model_id in model_ids:
        print(f"Prefetching model {model_id} into {cache_dir}", flush=True)
        path = snapshot_download(
            repo_id=model_id,
            repo_type="model",
            cache_dir=str(cache_dir),
            allow_patterns=list(allow_patterns),
            ignore_patterns=list(ignore_patterns),
            local_files_only=args.local_files_only,
        )
        rows.append(
            {
                "model_id": model_id,
                "snapshot_path": path,
                "allow_patterns": list(allow_patterns),
                "ignore_patterns": list(ignore_patterns),
            }
        )
        print(f"Prefetched {model_id} -> {path}", flush=True)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cache_dir": str(cache_dir),
        "models": rows,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prefetch Hugging Face model assets into Narval scratch cache.")
    parser.add_argument("--model-id", action="append", default=[])
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("/home/syin94/scratch/lora_health/data/hf_cache/transformers"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("/home/syin94/scratch/lora_health/data/hf_cache/prefetch_manifest.json"),
    )
    parser.add_argument("--allow-pattern", action="append", default=[])
    parser.add_argument("--ignore-pattern", action="append", default=[])
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
