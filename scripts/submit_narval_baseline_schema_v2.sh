#!/usr/bin/env bash
#SBATCH --job-name=lora_health_baseline_schema_v2
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
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
OUT_DIR="${PROJECT_ROOT}/results/baseline_schema_v2"

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

mkdir -p "${OUT_DIR}" "${PROJECT_ROOT}/slurm_logs"
cd "${CODE_DIR}"

python train/run_baseline.py \
  --gold eval/gold/synthetic_v0.jsonl \
  --out "${OUT_DIR}/predictions.jsonl" \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --cache-dir "${PROJECT_ROOT}/data/hf_cache/transformers" \
  --max-new-tokens 1536 \
  --prompt-version schema_v2 \
  --local-files-only

python eval/run_eval.py \
  --gold eval/gold/synthetic_v0.jsonl \
  --pred "${OUT_DIR}/predictions.jsonl" \
  --out "${OUT_DIR}/metrics.json" \
  --details-out "${OUT_DIR}/example_details.json"
