#!/usr/bin/env bash
#SBATCH --job-name=lora_health_smoke
#SBATCH --account=def-falmaham
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.out
#SBATCH --error=/home/syin94/scratch/lora_health/slurm_logs/%x_%j.err
#SBATCH --chdir=/home/syin94/scratch/lora_health

set -euo pipefail

PROJECT_ROOT="/home/syin94/scratch/lora_health"
THESIS_ROOT="/home/syin94/scratch/MEng_Project"

PROJECT_REAL="$(realpath -m "${PROJECT_ROOT}")"
PWD_REAL="$(pwd -P)"

case "${PWD_REAL}" in
  "${PROJECT_REAL}"*) ;;
  *) echo "Refusing to run outside ${PROJECT_ROOT}; PWD=${PWD_REAL}" >&2; exit 2 ;;
esac

if grep -R "${THESIS_ROOT}" -n configs 2>/dev/null; then
  echo "Refusing to run: thesis project path appears in runtime configs." >&2
  exit 3
fi

mkdir -p "${PROJECT_ROOT}/runs" "${PROJECT_ROOT}/slurm_logs"

echo "host=$(hostname)"
echo "pwd=${PWD}"
echo "job=${SLURM_JOB_ID:-local}"
echo "This is a smoke template. Replace with an explicit train/eval command after Phase 1-3 Go/No-Go."
