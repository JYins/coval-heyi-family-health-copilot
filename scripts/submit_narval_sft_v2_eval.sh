#!/usr/bin/env bash
#SBATCH --job-name=lora_health_sft_v2_eval
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
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
ADAPTER_DIR="${LORA_HEALTH_EVAL_ADAPTER_DIR:-${PROJECT_ROOT}/runs/qwen7b_lora_sft_v2}"
OUT_ROOT="${LORA_HEALTH_EVAL_OUT_ROOT:-${PROJECT_ROOT}/results/sft_v2_eval}"

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

mkdir -p "${OUT_ROOT}" "${PROJECT_ROOT}/slurm_logs"
cd "${CODE_DIR}"

run_eval_set() {
  local name="$1"
  local gold="$2"
  local product_limit="$3"
  local out_dir="${OUT_ROOT}/${name}"

  if [ ! -f "${gold}" ]; then
    echo "Missing gold file: ${CODE_DIR}/${gold}" >&2
    exit 5
  fi

  mkdir -p "${out_dir}"
  rm -f \
    "${out_dir}/predictions_raw.jsonl" \
    "${out_dir}/raw_outputs.jsonl" \
    "${out_dir}/metrics_raw.json" \
    "${out_dir}/example_details_raw.json" \
    "${out_dir}/predictions_normalized.jsonl" \
    "${out_dir}/normalization_report.json" \
    "${out_dir}/predictions_report_type_normalized.jsonl" \
    "${out_dir}/report_type_normalization_report.json" \
    "${out_dir}/predictions_report_type_template_summary.jsonl" \
    "${out_dir}/metrics_report_type_template_summary.json" \
    "${out_dir}/example_details_report_type_template_summary.json" \
    "${out_dir}/contract_validation_report_type_template_summary.json" \
    "${out_dir}/product_spine.sqlite" \
    "${out_dir}/product_spine_report.json" \
    "${out_dir}/product_spine_doctor_summary.md" \
    "${out_dir}/predictions_recovered.jsonl" \
    "${out_dir}/recovery_report.json" \
    "${out_dir}/predictions_recovered_normalized.jsonl" \
    "${out_dir}/recovered_normalization_report.json" \
    "${out_dir}/predictions_recovered_report_type_normalized.jsonl" \
    "${out_dir}/recovered_report_type_normalization_report.json" \
    "${out_dir}/predictions_recovered_report_type_template_summary.jsonl" \
    "${out_dir}/metrics_recovered_report_type_template_summary.json" \
    "${out_dir}/example_details_recovered_report_type_template_summary.json" \
    "${out_dir}/contract_validation_recovered_report_type_template_summary.json" \
    "${out_dir}/product_spine_recovered.sqlite" \
    "${out_dir}/product_spine_recovered_report.json" \
    "${out_dir}/product_spine_recovered_doctor_summary.md"

  python train/run_baseline.py \
    --gold "${gold}" \
    --out "${out_dir}/predictions_raw.jsonl" \
    --raw-out "${out_dir}/raw_outputs.jsonl" \
    --model-id Qwen/Qwen2.5-7B-Instruct \
    --cache-dir "${PROJECT_ROOT}/data/hf_cache/transformers" \
    --adapter-path "${ADAPTER_DIR}" \
    --max-new-tokens 1536 \
    --prompt-version schema_v3 \
    --local-files-only

  python eval/run_eval.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_raw.jsonl" \
    --out "${out_dir}/metrics_raw.json" \
    --details-out "${out_dir}/example_details_raw.json"

  python scripts/normalize_predictions.py \
    --pred "${out_dir}/predictions_raw.jsonl" \
    --out "${out_dir}/predictions_normalized.jsonl" \
    --report "${out_dir}/normalization_report.json"

  python scripts/normalize_report_types.py \
    --pred "${out_dir}/predictions_normalized.jsonl" \
    --out "${out_dir}/predictions_report_type_normalized.jsonl" \
    --report "${out_dir}/report_type_normalization_report.json"

  python scripts/template_doctor_summary.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_report_type_normalized.jsonl" \
    --out "${out_dir}/predictions_report_type_template_summary.jsonl"

  python eval/run_eval.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_report_type_template_summary.jsonl" \
    --out "${out_dir}/metrics_report_type_template_summary.json" \
    --details-out "${out_dir}/example_details_report_type_template_summary.json"

  python scripts/validate_predictions.py \
    --predictions "${out_dir}/predictions_report_type_template_summary.jsonl" \
    --out "${out_dir}/contract_validation_report_type_template_summary.json"

  python src/product_spine.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_report_type_template_summary.jsonl" \
    --database "${out_dir}/product_spine.sqlite" \
    --out "${out_dir}/product_spine_report.json" \
    --markdown-out "${out_dir}/product_spine_doctor_summary.md" \
    --limit "${product_limit}"

  python scripts/recover_predictions_from_raw_outputs.py \
    --raw-outputs "${out_dir}/raw_outputs.jsonl" \
    --out "${out_dir}/predictions_recovered.jsonl" \
    --report "${out_dir}/recovery_report.json"

  python scripts/normalize_predictions.py \
    --pred "${out_dir}/predictions_recovered.jsonl" \
    --out "${out_dir}/predictions_recovered_normalized.jsonl" \
    --report "${out_dir}/recovered_normalization_report.json"

  python scripts/normalize_report_types.py \
    --pred "${out_dir}/predictions_recovered_normalized.jsonl" \
    --out "${out_dir}/predictions_recovered_report_type_normalized.jsonl" \
    --report "${out_dir}/recovered_report_type_normalization_report.json"

  python scripts/template_doctor_summary.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_recovered_report_type_normalized.jsonl" \
    --out "${out_dir}/predictions_recovered_report_type_template_summary.jsonl"

  python eval/run_eval.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_recovered_report_type_template_summary.jsonl" \
    --out "${out_dir}/metrics_recovered_report_type_template_summary.json" \
    --details-out "${out_dir}/example_details_recovered_report_type_template_summary.json"

  python scripts/validate_predictions.py \
    --predictions "${out_dir}/predictions_recovered_report_type_template_summary.jsonl" \
    --out "${out_dir}/contract_validation_recovered_report_type_template_summary.json"

  python src/product_spine.py \
    --gold "${gold}" \
    --pred "${out_dir}/predictions_recovered_report_type_template_summary.jsonl" \
    --database "${out_dir}/product_spine_recovered.sqlite" \
    --out "${out_dir}/product_spine_recovered_report.json" \
    --markdown-out "${out_dir}/product_spine_recovered_doctor_summary.md" \
    --limit "${product_limit}"
}

run_eval_set "synthetic_v0" "eval/gold/synthetic_v0.jsonl" 10
run_eval_set "medication_contrast_v0" "eval/gold/medication_contrast_v0.jsonl" 4
run_eval_set "safety_onset_edge_v1_1" "eval/gold/safety_onset_edge_v1_1.jsonl" 6
