# Coval HeYi Web Demo

Family-facing health memory UI for the LoRA health project.

## Current Demo Behavior

- `智能整理` calls the FastAPI ingestion route and creates a persisted pending candidate.
- The main workspace stays write-locked until the API reports the fail-closed
  `synthetic_public_only` gate and the user acknowledges that the input is fictional/public.
- Review rows are editable; `确认保存到健康记忆` creates canonical v1 only after review.
- Later edits create a new version, and `撤销到上一版` appends another version rather than overwriting history.
- API/SQLite/mock-provider failures are visible and durable writes are disabled while offline.
- Arbitrary note/source/date input and API-backed member creation replace the old read-only demo path.
- Source text is persisted before inference; retryable failures survive reload in a recovery inbox protected by expiring leases.
- The main review area promotes the doctor-facing summary, while the right rail shows a concrete visit-prep checklist and missing-field checklist.
- Mobile opens directly on `新建记录`, with member selection, OCR/voice/blood-pressure modes, source/date/missing-field context, and save-after-review behavior.
- `本地 OCR 待接入` is intentionally disabled in the public demo so no real files are read.
- Reminder and weekly-report cards are explicitly labeled as planned; no worker is implied.
- README screenshots are stored in `docs/assets/coval-heyi-desktop.png` and `docs/assets/coval-heyi-mobile.png`.

## Stack

- Next.js App Router
- React
- TypeScript
- FastAPI backend contract in `src/serve/coval_health_api.py`

## Local Run

```powershell
cd <repo-root>\apps\coval-health-web
npm ci
npm run dev
```

FastAPI demo contract:

```powershell
cd <repo-root>
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
- `POST /ingestions`
- `PATCH /records/{id}/candidate`
- `POST /records/{id}/approve`
- `PATCH /records/{id}`
- `POST /records/{id}/undo`
- `GET /records/{id}/versions`
- `GET /timeline?member_id=mom`

The frontend reads `NEXT_PUBLIC_COVAL_API_BASE_URL` and falls back to `http://127.0.0.1:8000`.

The demo uses synthetic/public records only. The acknowledgement is a deliberate
release boundary, not a content detector: this build must not receive real family
or patient data. It does not diagnose, prescribe, or adjust medication.

## Quality checks

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File scripts\run_local_quality.ps1
```

Browser tests use a temporary synthetic-only SQLite database and dedicated local
ports. See `tests-e2e/durable-memory.spec.ts`.

Current model evidence shown in the UI:

- Base model: `Qwen/Qwen2.5-7B-Instruct`
- Historical research candidate: `LoRA SFT v2 + deterministic summary patch` (deployment blocked)
- Default product runtime: `mock-rules-v2`; local v2 NF4 has also completed a
  real browser/SQLite synthetic E2E but remains opt-in: the frozen same-local
  unquantized comparator was not runnable on this GPU, while false refusals and
  descriptive historical gaps block deployment.
- Runtime health distinguishes `mock`, benchmark-only `transformers_base`,
  `transformers_adapter`, and `llama_cpp`;
  missing local artifacts produce a visible error instead of mock fallback.
- Latest ablation: `SFT v3 completed; not adopted`
- Evidence source: `GET /model-evidence`, backed by committed curated summaries under `artifacts/public/`

## Product Position

`Coval HeYi` turns messy family notes, OCR text, and future voice snippets into:

- structured health facts;
- an AI memo lineage from capture to review to local memory to doctor briefing;
- a longitudinal family timeline;
- a visit-prep communication summary and checklist;
- missing-field prompts that are visible before save;
- safety refusal or crisis escalation flags;
- model/eval evidence from the LoRA project.
