#!/usr/bin/env bash
set -euo pipefail

REMOTE_ROOT="${REMOTE_ROOT:-/home/syin94/scratch/lora_health}"
ADAPTER_DIR="${ADAPTER_DIR:-${REMOTE_ROOT}/runs/qwen7b_lora_sft_v2}"
REPO_ID="${HF_REPO_ID:-}"
RESULTS_DIR="${RESULTS_DIR:-${REMOTE_ROOT}/results}"

if [[ -z "${REPO_ID}" ]]; then
  echo "Set HF_REPO_ID first, for example: export HF_REPO_ID='username/coval-heyi-qwen2p5-7b-lora-v2'" >&2
  exit 2
fi

if [[ ! -d "${ADAPTER_DIR}" ]]; then
  echo "Adapter directory not found: ${ADAPTER_DIR}" >&2
  exit 2
fi

for required_file in adapter_config.json adapter_model.safetensors; do
  if [[ ! -f "${ADAPTER_DIR}/${required_file}" ]]; then
    echo "Missing required adapter file: ${ADAPTER_DIR}/${required_file}" >&2
    exit 2
  fi
done

if ! command -v hf >/dev/null 2>&1; then
  echo "hf CLI is not available in this environment." >&2
  echo "Install huggingface_hub in the active Narval venv, then rerun." >&2
  exit 2
fi

echo "Preparing to upload adapter only."
echo "Repo: ${REPO_ID}"
echo "Adapter: ${ADAPTER_DIR}"
echo "Results root: ${RESULTS_DIR}"
echo
echo "Authentication:"
echo "- Preferred: run 'hf auth login' interactively before this script."
echo "- Alternative: export HF_TOKEN only in this shell session."
echo "- Never write tokens into repo files or logs."
echo

hf upload "${REPO_ID}" "${ADAPTER_DIR}" . \
  --type model \
  --include "adapter_config.json" \
  --include "adapter_model.safetensors" \
  --include "tokenizer.json" \
  --include "tokenizer_config.json" \
  --include "special_tokens_map.json" \
  --include "sft_run_manifest.json"

echo
echo "Adapter upload command finished. Add/update the model card separately before making the repo public or gated."
