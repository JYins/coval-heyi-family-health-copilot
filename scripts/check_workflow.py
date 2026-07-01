from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".next",
    "dist",
    "coverage",
    "graphify-out",
    "data/private",
    "checkpoints",
    "models",
    "adapters",
    "outputs",
}
SECRET_PATTERNS = [
    re.compile(r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    re.compile(r"(?m)^HUGGINGFACE_TOKEN[ \t]*=[ \t]*[^#\r\n]+"),
    re.compile(r"(?m)^OPENAI_API_KEY[ \t]*=[ \t]*[^#\r\n]+"),
    re.compile(r"(?im)^(password|passwd|secret|token)[ \t]*[:=][ \t]*['\"]?[^'\"\s]{8,}"),
]
REQUIRED_FILES = [
    "AGENTS.md",
    ".gitignore",
    "docs/PROJECT_BRIEF.md",
    "docs/PLAN.md",
    "docs/REMOTE_NARVAL.md",
    "eval/gold/synthetic_v0.jsonl",
    "eval/gold/medication_contrast_v0.jsonl",
    "eval/run_eval.py",
]
SLURM_FILES = [
    "scripts/submit_narval.sh",
    "scripts/submit_narval_data_prep.sh",
    "scripts/submit_narval_baseline.sh",
    "scripts/submit_narval_baseline_schema_v2.sh",
    "scripts/submit_narval_baseline_schema_v3.sh",
    "scripts/submit_narval_medication_contrast_schema_v3.sh",
    "scripts/submit_narval_medication_contrast_schema_v4.sh",
    "scripts/submit_narval_sft_smoke.sh",
    "scripts/submit_narval_sft_smoke_eval.sh",
    "scripts/submit_narval_sft_v1.sh",
    "scripts/submit_narval_sft_v1_eval.sh",
    "scripts/submit_narval_sft_v1_eval_v1_1.sh",
    "scripts/submit_narval_sft_v2.sh",
    "scripts/submit_narval_sft_v2_eval.sh",
]


def main() -> None:
    errors: list[str] = []
    errors.extend(check_required_files())
    errors.extend(check_secret_patterns())
    errors.extend(check_slurm_files())
    errors.extend(check_dataset_manifest())

    if errors:
        print("workflow check failed:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("workflow check ok")


def check_required_files() -> list[str]:
    errors = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    return errors


def check_secret_patterns() -> list[str]:
    errors = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret pattern {pattern.pattern!r} in {rel}")
    return errors


def check_slurm_files() -> list[str]:
    errors = []
    for rel in SLURM_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "#SBATCH --job-name=lora_health_" not in text:
            errors.append(f"{rel} missing lora_health_ Slurm job prefix")
        if "#SBATCH --chdir=/home/syin94/scratch/lora_health" not in text:
            errors.append(f"{rel} missing lora_health --chdir")
        if "/home/syin94/scratch/MEng_Project" not in text:
            errors.append(f"{rel} missing explicit thesis-root guard")
    return errors


def check_dataset_manifest() -> list[str]:
    path = ROOT / "data/dataset_manifest.json"
    if not path.exists():
        return ["missing data/dataset_manifest.json"]
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for row in data.get("datasets", []):
        if not row.get("source"):
            errors.append(f"dataset missing source: {row.get('id')}")
        if row.get("license") in {"unknown", "", None}:
            errors.append(f"dataset missing license review state: {row.get('id')}")
    return errors


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        parts = set(path.relative_to(ROOT).parts)
        if any(rel == skip or rel.startswith(f"{skip}/") for skip in SKIP_DIRS):
            continue
        if parts.intersection(SKIP_DIRS):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tgz"}:
            continue
        yield path


if __name__ == "__main__":
    main()
