#!/usr/bin/env bash
#SBATCH --job-name=lora_health_sft_v3
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=05:00:00
#SBATCH --output=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.out
#SBATCH --error=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.err
#SBATCH --chdir=/home/syin94/scratch/lora_health

set -euo pipefail

PROJECT_ROOT="/home/syin94/scratch/lora_health"
CODE_DIR="${PROJECT_ROOT}/code"
THESIS_ROOT="/home/syin94/scratch/MEng_Project"
GCC_MODULE="${GCC_MODULE:-gcc/12.3}"
ARROW_MODULE="${ARROW_MODULE:-arrow/24.0.0}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.11}"
CONFIG_PATH="${CODE_DIR}/configs/qwen7b_lora_sft_v3.yaml"
OUT_DIR="${PROJECT_ROOT}/runs/qwen7b_lora_sft_v3"

if [ "${LORA_HEALTH_APPROVED_SFT_V3:-0}" != "1" ]; then
  echo "Refusing to submit SFT v3: set LORA_HEALTH_APPROVED_SFT_V3=1 only after explicit user approval." >&2
  exit 4
fi

PROJECT_REAL="$(realpath -m "${PROJECT_ROOT}")"
PWD_REAL="$(pwd -P)"

case "${PWD_REAL}" in
  "${PROJECT_REAL}"*) ;;
  *) echo "Refusing to run outside ${PROJECT_ROOT}; PWD=${PWD_REAL}" >&2; exit 2 ;;
esac

if grep -R "${THESIS_ROOT}" -n \
  --include='*.py' \
  --include='*.json' \
  --include='*.yaml' \
  --include='*.yml' \
  --include='*.toml' \
  --include='*.sh' \
  "${CODE_DIR}/configs" "${CODE_DIR}/train" 2>/dev/null; then
  echo "Refusing to run: thesis project path appears in runtime configs or train code." >&2
  exit 3
fi

if [ ! -x "${PROJECT_ROOT}/venv/bin/python" ]; then
  bash "${CODE_DIR}/scripts/narval_bootstrap.sh"
fi

if command -v module >/dev/null 2>&1; then
  module --force purge || true
  module load StdEnv/2023 || true
  module load "${GCC_MODULE}" || true
  module load "${ARROW_MODULE}" || true
  module load "${PYTHON_MODULE}" || true
fi

source "${PROJECT_ROOT}/venv/bin/activate"
export HF_HOME="${PROJECT_ROOT}/data/hf_cache"
export HF_DATASETS_CACHE="${PROJECT_ROOT}/data/hf_cache/datasets"
export TRANSFORMERS_CACHE="${PROJECT_ROOT}/data/hf_cache/transformers"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

mkdir -p "${PROJECT_ROOT}/runs" "${PROJECT_ROOT}/slurm_logs" "${PROJECT_ROOT}/results"
cd "${CODE_DIR}"

python train/build_sft_v3_dataset.py --out-dir data/public/sft_v3

python scripts/validate_sft_smoke_dataset.py \
  --train-jsonl data/public/sft_v3/train.jsonl \
  --val-jsonl data/public/sft_v3/val.jsonl \
  --manifest data/public/sft_v3/manifest.json \
  --gold eval/gold/synthetic_v0.jsonl eval/gold/medication_contrast_v0.jsonl eval/gold/safety_onset_edge_v1_1.jsonl \
  --report "${PROJECT_ROOT}/results/sft_v3_validation_remote.json"

python train/train_sft.py \
  --config "${CONFIG_PATH}" \
  --train-jsonl data/public/sft_v3/train.jsonl \
  --val-jsonl data/public/sft_v3/val.jsonl \
  --output-dir "${OUT_DIR}" \
  --local-files-only
