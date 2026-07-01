#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/syin94/scratch/lora_health}"
MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-7B-Instruct}"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/venv}"
GCC_MODULE="${GCC_MODULE:-gcc/12.3}"
ARROW_MODULE="${ARROW_MODULE:-arrow/24.0.0}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.11}"

case "${PROJECT_ROOT}" in
  /home/syin94/scratch/lora_health*) ;;
  *) echo "Refusing unsafe PROJECT_ROOT=${PROJECT_ROOT}" >&2; exit 2 ;;
esac

export HF_HOME="${PROJECT_ROOT}/data/hf_cache"
export HF_DATASETS_CACHE="${PROJECT_ROOT}/data/hf_cache/datasets"
export TRANSFORMERS_CACHE="${PROJECT_ROOT}/data/hf_cache/transformers"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

MODEL_CACHE="${TRANSFORMERS_CACHE}/models--${MODEL_ID/\//--}"
if [ ! -d "${MODEL_CACHE}/snapshots" ]; then
  echo "Missing model cache snapshots at ${MODEL_CACHE}/snapshots" >&2
  exit 4
fi

SNAPSHOT_DIR="$(find "${MODEL_CACHE}/snapshots" -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
if [ -z "${SNAPSHOT_DIR}" ]; then
  echo "No snapshot directory found under ${MODEL_CACHE}/snapshots" >&2
  exit 5
fi

for required in config.json tokenizer.json tokenizer_config.json model.safetensors.index.json; do
  if [ ! -e "${SNAPSHOT_DIR}/${required}" ]; then
    echo "Missing ${SNAPSHOT_DIR}/${required}" >&2
    exit 6
  fi
done

SHARD_COUNT="$(find "${SNAPSHOT_DIR}" -maxdepth 1 -name 'model-*.safetensors' | wc -l)"
if [ "${SHARD_COUNT}" -lt 1 ]; then
  echo "No safetensors shards found in ${SNAPSHOT_DIR}" >&2
  exit 7
fi

echo "model_id=${MODEL_ID}"
echo "snapshot_dir=${SNAPSHOT_DIR}"
echo "safetensors_shards=${SHARD_COUNT}"
echo "hf_cache_ok=true"
