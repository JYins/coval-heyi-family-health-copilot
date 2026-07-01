#!/usr/bin/env bash
#SBATCH --job-name=lora_health_sft_v1_eval_v1_1
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
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
ADAPTER_DIR="${PROJECT_ROOT}/runs/qwen7b_lora_sft_v1"
OUT_ROOT="${PROJECT_ROOT}/results/sft_v1_eval_v1_1"
GOLD="eval/gold/safety_onset_edge_v1_1.jsonl"

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

if [ ! -f "${ADAPTER_DIR}/adapter_model.safetensors" ]; then
  echo "Missing adapter: ${ADAPTER_DIR}/adapter_model.safetensors" >&2
  exit 4
fi

if [ ! -f "${CODE_DIR}/${GOLD}" ]; then
  echo "Missing gold file: ${CODE_DIR}/${GOLD}" >&2
  exit 5
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

OUT_DIR="${OUT_ROOT}/safety_onset_edge_v1_1"
mkdir -p "${OUT_DIR}" "${PROJECT_ROOT}/slurm_logs"
cd "${CODE_DIR}"

rm -f \
  "${OUT_DIR}/predictions_raw.jsonl" \
  "${OUT_DIR}/raw_outputs.jsonl" \
  "${OUT_DIR}/metrics_raw.json" \
  "${OUT_DIR}/example_details_raw.json" \
  "${OUT_DIR}/predictions_normalized.jsonl" \
  "${OUT_DIR}/normalization_report.json" \
  "${OUT_DIR}/predictions_report_type_normalized.jsonl" \
  "${OUT_DIR}/report_type_normalization_report.json" \
  "${OUT_DIR}/predictions_report_type_template_summary.jsonl" \
  "${OUT_DIR}/metrics_report_type_template_summary.json" \
  "${OUT_DIR}/example_details_report_type_template_summary.json" \
  "${OUT_DIR}/contract_validation_report_type_template_summary.json" \
  "${OUT_DIR}/product_spine.sqlite" \
  "${OUT_DIR}/product_spine_report.json" \
  "${OUT_DIR}/product_spine_doctor_summary.md" \
  "${OUT_DIR}/predictions_recovered.jsonl" \
  "${OUT_DIR}/recovery_report.json" \
  "${OUT_DIR}/predictions_recovered_normalized.jsonl" \
  "${OUT_DIR}/recovered_normalization_report.json" \
  "${OUT_DIR}/predictions_recovered_report_type_normalized.jsonl" \
  "${OUT_DIR}/recovered_report_type_normalization_report.json" \
  "${OUT_DIR}/predictions_recovered_report_type_template_summary.jsonl" \
  "${OUT_DIR}/metrics_recovered_report_type_template_summary.json" \
  "${OUT_DIR}/example_details_recovered_report_type_template_summary.json" \
  "${OUT_DIR}/contract_validation_recovered_report_type_template_summary.json" \
  "${OUT_DIR}/product_spine_recovered.sqlite" \
  "${OUT_DIR}/product_spine_recovered_report.json" \
  "${OUT_DIR}/product_spine_recovered_doctor_summary.md"

python train/run_baseline.py \
  --gold "${GOLD}" \
  --out "${OUT_DIR}/predictions_raw.jsonl" \
  --raw-out "${OUT_DIR}/raw_outputs.jsonl" \
  --model-id Qwen/Qwen2.5-7B-Instruct \
  --cache-dir "${PROJECT_ROOT}/data/hf_cache/transformers" \
  --adapter-path "${ADAPTER_DIR}" \
  --max-new-tokens 1536 \
  --prompt-version schema_v3 \
  --local-files-only

python eval/run_eval.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_raw.jsonl" \
  --out "${OUT_DIR}/metrics_raw.json" \
  --details-out "${OUT_DIR}/example_details_raw.json"

python scripts/normalize_predictions.py \
  --pred "${OUT_DIR}/predictions_raw.jsonl" \
  --out "${OUT_DIR}/predictions_normalized.jsonl" \
  --report "${OUT_DIR}/normalization_report.json"

python scripts/normalize_report_types.py \
  --pred "${OUT_DIR}/predictions_normalized.jsonl" \
  --out "${OUT_DIR}/predictions_report_type_normalized.jsonl" \
  --report "${OUT_DIR}/report_type_normalization_report.json"

python scripts/template_doctor_summary.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_report_type_normalized.jsonl" \
  --out "${OUT_DIR}/predictions_report_type_template_summary.jsonl"

python eval/run_eval.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_report_type_template_summary.jsonl" \
  --out "${OUT_DIR}/metrics_report_type_template_summary.json" \
  --details-out "${OUT_DIR}/example_details_report_type_template_summary.json"

python scripts/validate_predictions.py \
  --predictions "${OUT_DIR}/predictions_report_type_template_summary.jsonl" \
  --out "${OUT_DIR}/contract_validation_report_type_template_summary.json"

python src/product_spine.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_report_type_template_summary.jsonl" \
  --database "${OUT_DIR}/product_spine.sqlite" \
  --out "${OUT_DIR}/product_spine_report.json" \
  --markdown-out "${OUT_DIR}/product_spine_doctor_summary.md" \
  --limit 6

python scripts/recover_predictions_from_raw_outputs.py \
  --raw-outputs "${OUT_DIR}/raw_outputs.jsonl" \
  --out "${OUT_DIR}/predictions_recovered.jsonl" \
  --report "${OUT_DIR}/recovery_report.json"

python scripts/normalize_predictions.py \
  --pred "${OUT_DIR}/predictions_recovered.jsonl" \
  --out "${OUT_DIR}/predictions_recovered_normalized.jsonl" \
  --report "${OUT_DIR}/recovered_normalization_report.json"

python scripts/normalize_report_types.py \
  --pred "${OUT_DIR}/predictions_recovered_normalized.jsonl" \
  --out "${OUT_DIR}/predictions_recovered_report_type_normalized.jsonl" \
  --report "${OUT_DIR}/recovered_report_type_normalization_report.json"

python scripts/template_doctor_summary.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_recovered_report_type_normalized.jsonl" \
  --out "${OUT_DIR}/predictions_recovered_report_type_template_summary.jsonl"

python eval/run_eval.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_recovered_report_type_template_summary.jsonl" \
  --out "${OUT_DIR}/metrics_recovered_report_type_template_summary.json" \
  --details-out "${OUT_DIR}/example_details_recovered_report_type_template_summary.json"

python scripts/validate_predictions.py \
  --predictions "${OUT_DIR}/predictions_recovered_report_type_template_summary.jsonl" \
  --out "${OUT_DIR}/contract_validation_recovered_report_type_template_summary.json"

python src/product_spine.py \
  --gold "${GOLD}" \
  --pred "${OUT_DIR}/predictions_recovered_report_type_template_summary.jsonl" \
  --database "${OUT_DIR}/product_spine_recovered.sqlite" \
  --out "${OUT_DIR}/product_spine_recovered_report.json" \
  --markdown-out "${OUT_DIR}/product_spine_recovered_doctor_summary.md" \
  --limit 6
