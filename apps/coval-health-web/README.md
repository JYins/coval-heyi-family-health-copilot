# Coval HeYi Web Demo

Family-facing health memory UI for the LoRA health project.

## Stack

- Next.js App Router
- React
- TypeScript
- FastAPI backend contract in `src/serve/coval_health_api.py`

## Local Run

```powershell
cd D:\lora\apps\coval-health-web
npm ci
npm run dev
```

FastAPI demo contract:

```powershell
cd D:\lora
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-web.txt
.\.venv\Scripts\uvicorn src.serve.coval_health_api:app --reload --port 8000
```

Useful API routes:

- `GET /health`
- `GET /family-members`
- `GET /model-evidence`
- `GET /product-lineage`
- `POST /structure`

The frontend reads `NEXT_PUBLIC_COVAL_API_BASE_URL` and falls back to `http://127.0.0.1:8000`.

The demo uses synthetic records only. It does not diagnose, prescribe, or adjust medication.

Current model evidence shown in the UI:

- Base model: `Qwen/Qwen2.5-7B-Instruct`
- Product/demo default: `LoRA SFT v2 + deterministic summary patch`
- Latest ablation: `SFT v3 completed; not adopted`
- Evidence source: `GET /model-evidence`, backed by local result files under `results/`

## Product Position

`Coval HeYi` turns messy family notes, OCR text, and future voice snippets into:

- structured health facts;
- an AI memo lineage from capture to review to local memory to doctor briefing;
- a longitudinal family timeline;
- a visit-prep communication summary;
- safety refusal or crisis escalation flags;
- model/eval evidence from the LoRA project.
