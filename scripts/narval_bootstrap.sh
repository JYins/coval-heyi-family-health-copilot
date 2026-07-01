#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/syin94/scratch/lora_health}"
CODE_DIR="${CODE_DIR:-${PROJECT_ROOT}/code}"
THESIS_ROOT="${THESIS_ROOT:-/home/syin94/scratch/MEng_Project}"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/venv}"
PYTHON_MODULE="${PYTHON_MODULE:-python/3.11}"
GCC_MODULE="${GCC_MODULE:-gcc/12.3}"
ARROW_MODULE="${ARROW_MODULE:-arrow/24.0.0}"

case "${PROJECT_ROOT}" in
  /home/syin94/scratch/lora_health*) ;;
  *) echo "Refusing unsafe PROJECT_ROOT=${PROJECT_ROOT}" >&2; exit 2 ;;
esac

case "${PWD}" in
  "${THESIS_ROOT}"*) echo "Refusing to run inside thesis root: ${PWD}" >&2; exit 3 ;;
esac

mkdir -p \
  "${PROJECT_ROOT}/code" \
  "${PROJECT_ROOT}/data/hf_cache" \
  "${PROJECT_ROOT}/data/public" \
  "${PROJECT_ROOT}/data/raw" \
  "${PROJECT_ROOT}/data/processed" \
  "${PROJECT_ROOT}/models" \
  "${PROJECT_ROOT}/runs" \
  "${PROJECT_ROOT}/slurm_logs" \
  "${PROJECT_ROOT}/tmp"

cd "${PROJECT_ROOT}"

echo "Narval lora_health bootstrap"
echo "host=$(hostname)"
echo "user=$(whoami)"
echo "project_root=${PROJECT_ROOT}"
echo "code_dir=${CODE_DIR}"
echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if command -v diskusage_report >/dev/null 2>&1; then
  diskusage_report || true
else
  echo "diskusage_report not found; skipping quota print"
fi

if command -v module >/dev/null 2>&1; then
  module --force purge || true
  module load StdEnv/2023 || true
  module load "${GCC_MODULE}" || true
  module load "${ARROW_MODULE}" || true
  module load "${PYTHON_MODULE}" || true
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "${PYTHON_BIN}" ]; then
  echo "No python found after module setup" >&2
  exit 4
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip wheel

if [ -f "${CODE_DIR}/requirements-narval.txt" ]; then
  python -m pip install -r "${CODE_DIR}/requirements-narval.txt"
else
  echo "requirements-narval.txt not found at ${CODE_DIR}; skipping pip project deps"
fi

cat > "${PROJECT_ROOT}/REMOTE_LAYOUT.txt" <<EOF
Remote project root: ${PROJECT_ROOT}
Code: ${CODE_DIR}
Venv: ${VENV_DIR}
Public data: ${PROJECT_ROOT}/data/public
HF cache: ${PROJECT_ROOT}/data/hf_cache
Runs: ${PROJECT_ROOT}/runs
Slurm logs: ${PROJECT_ROOT}/slurm_logs

Rules:
- Do not read or write ${THESIS_ROOT}
- Slurm job names must start with lora_health_
- Only public or synthetic data belongs here
EOF

echo "bootstrap_done=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
