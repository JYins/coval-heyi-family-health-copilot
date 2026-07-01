#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/syin94/scratch/lora_health}"
CODE_DIR="${CODE_DIR:-${PROJECT_ROOT}/code}"
THESIS_ROOT="${THESIS_ROOT:-/home/syin94/scratch/MEng_Project}"

case "${PROJECT_ROOT}" in
  /home/syin94/scratch/lora_health*) ;;
  *) echo "Refusing unsafe PROJECT_ROOT=${PROJECT_ROOT}" >&2; exit 2 ;;
esac

case "${PWD}" in
  "${THESIS_ROOT}"*) echo "Refusing to run inside thesis root: ${PWD}" >&2; exit 3 ;;
esac

cd "${PROJECT_ROOT}"

echo "== lora_health remote status =="
echo "host=$(hostname)"
echo "user=$(whoami)"
echo "pwd=${PWD}"
echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo
echo "== quota =="
if command -v diskusage_report >/dev/null 2>&1; then
  diskusage_report || true
else
  echo "diskusage_report not found"
fi

echo
echo "== project layout =="
for path in code data data/public runs slurm_logs; do
  if [ -e "${PROJECT_ROOT}/${path}" ]; then
    du -sh "${PROJECT_ROOT}/${path}" 2>/dev/null || true
  else
    echo "missing ${PROJECT_ROOT}/${path}"
  fi
done
if [ -x "${PROJECT_ROOT}/venv/bin/python" ]; then
  echo "venv: ready at ${PROJECT_ROOT}/venv"
else
  echo "venv: missing ${PROJECT_ROOT}/venv/bin/python"
fi
if [ -d "${PROJECT_ROOT}/data/hf_cache" ]; then
  echo "hf_cache: present at ${PROJECT_ROOT}/data/hf_cache"
else
  echo "hf_cache: missing ${PROJECT_ROOT}/data/hf_cache"
fi

echo
echo "== slurm queue =="
squeue -u "$(whoami)" 2>/dev/null || true

echo
echo "== public data manifest =="
if [ -f "${PROJECT_ROOT}/data/public/download_manifest.json" ]; then
  python - <<'PY'
import json
from pathlib import Path

path = Path("/home/syin94/scratch/lora_health/data/public/download_manifest.json")
data = json.loads(path.read_text(encoding="utf-8"))
print("created_at=" + str(data.get("created_at")))
for row in data.get("datasets", []):
    print(f"{row.get('local_id')} {row.get('config')} {row.get('split')} rows={row.get('rows_written')} path={row.get('path')}")
PY
else
  echo "missing ${PROJECT_ROOT}/data/public/download_manifest.json"
fi

echo
echo "== recent slurm logs =="
if [ -d "${PROJECT_ROOT}/slurm_logs" ]; then
  find "${PROJECT_ROOT}/slurm_logs" -maxdepth 1 -type f -printf "%TY-%Tm-%Td %TH:%TM %p\n" 2>/dev/null | sort | tail -20 || true
fi

echo
echo "== thesis path guard =="
if [ -d "${CODE_DIR}/configs" ] && grep -R "${THESIS_ROOT}" -n "${CODE_DIR}/configs" 2>/dev/null; then
  echo "warning: thesis path appears in runtime configs" >&2
  exit 4
fi
echo "ok"
