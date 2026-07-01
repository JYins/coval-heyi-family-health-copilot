#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/syin94/scratch/lora_health}"
CODE_DIR="${CODE_DIR:-${PROJECT_ROOT}/code}"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/venv}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
GCC_MODULE="${GCC_MODULE:-gcc/12.3}"
ARROW_MODULE="${ARROW_MODULE:-arrow/24.0.0}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.11}"

case "${PROJECT_ROOT}" in
  /home/syin94/scratch/lora_health*) ;;
  *) echo "Refusing unsafe PROJECT_ROOT=${PROJECT_ROOT}" >&2; exit 2 ;;
esac

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo "Missing venv at ${VENV_DIR}. Run scripts/narval_bootstrap.sh first." >&2
  exit 3
fi

cd "${PROJECT_ROOT}"

if command -v module >/dev/null 2>&1; then
  module --force purge || true
  module load StdEnv/2023 || true
  module load "${GCC_MODULE}" || true
  module load "${ARROW_MODULE}" || true
  module load "${PYTHON_MODULE}" || true
fi

source "${VENV_DIR}/bin/activate"

export HF_HOME="${PROJECT_ROOT}/data/hf_cache"
export HF_DATASETS_CACHE="${PROJECT_ROOT}/data/hf_cache/datasets"
export TRANSFORMERS_CACHE="${PROJECT_ROOT}/data/hf_cache/transformers"

python "${CODE_DIR}/scripts/prefetch_hf_assets.py" \
  --model-id "${MODEL_ID}" \
  --cache-dir "${TRANSFORMERS_CACHE}" \
  --manifest "${PROJECT_ROOT}/data/hf_cache/prefetch_manifest.json"
