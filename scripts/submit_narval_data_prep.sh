#!/usr/bin/env bash
#SBATCH --job-name=lora_health_data_prep
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.out
#SBATCH --error=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.err
#SBATCH --chdir=/home/syin94/scratch/lora_health

set -euo pipefail

PROJECT_ROOT="/home/syin94/scratch/lora_health"
CODE_DIR="${PROJECT_ROOT}/code"
THESIS_ROOT="/home/syin94/scratch/MEng_Project"

PROJECT_REAL="$(realpath -m "${PROJECT_ROOT}")"
PWD_REAL="$(pwd -P)"

case "${PWD_REAL}" in
  "${PROJECT_REAL}"*) ;;
  *) echo "Refusing to run outside ${PROJECT_ROOT}; PWD=${PWD_REAL}" >&2; exit 2 ;;
esac

if grep -R "${THESIS_ROOT}" -n "${CODE_DIR}/configs" 2>/dev/null; then
  echo "Refusing to run: thesis project path appears in runtime configs." >&2
  exit 3
fi

mkdir -p "${PROJECT_ROOT}/slurm_logs" "${PROJECT_ROOT}/runs"

if [ ! -x "${PROJECT_ROOT}/venv/bin/python" ]; then
  bash "${CODE_DIR}/scripts/narval_bootstrap.sh"
fi

MAX_ROWS="${MAX_ROWS:-5000}" bash "${CODE_DIR}/scripts/narval_pull_data.sh"
