# Coval HeYi Product Packaging Plan

Status: draft for portfolio/product packaging.

## IP And Release Posture

- Keep the GitHub repository private while the product, datasets, and adapter-card wording are still moving.
- Do not add an open-source license yet. Without a license, outsiders do not automatically receive reuse rights.
- Hugging Face should start as a private or gated model repository.
- Public-facing artifacts may include only synthetic/public data, eval metrics, model card text, and adapter metadata.
- Never upload real family records, private patient data, local SQLite databases, secrets, or Narval logs containing credentials.

Recommended first public trace:

- Private or gated HF adapter repo: `coval-heyi-qwen2p5-7b-lora-v2`.
- Model card documents:
  - base model: `Qwen/Qwen2.5-7B-Instruct`;
  - current adapter: `LoRA SFT v2 + deterministic summary patch`;
  - v3 ablation: completed, measured, not adopted;
  - safety boundary: record organization only, no diagnosis, prescription, or medication adjustment.
- GitHub can stay private until the web app, Docker path, and README are clean.

## Hugging Face Upload Flow

Do not send account passwords in chat. Use one of these safe login paths:

- Preferred on Narval: run `hf auth login` interactively and paste a token into the terminal prompt.
- Preferred for one-shot upload: set `HF_TOKEN` only in the current shell session.
- Never commit HF tokens, passwords, MFA codes, or private keys.

2026-06-30 local CLI note:

- The project `.venv` has the modern Hugging Face CLI installed as `hf`.
- The old `huggingface-cli` command is deprecated; use `hf auth login`, `hf auth whoami`, and `hf upload`.
- Use `scripts/hf_local_login.ps1` for local Windows login checks. It sets UTF-8 terminal environment variables and never writes tokens into repo files.
- The Codex Hugging Face connector can be authenticated separately from local CLI auth. Connector identity does not automatically provide a local `HF_TOKEN`.

Why upload from Narval:

- The adapter already lives under `/home/syin94/scratch/lora_health/runs/qwen7b_lora_sft_v2`.
- Uploading from Narval avoids copying large adapter files back to Windows.
- If Narval outbound networking or login fails, pull the adapter to Windows and upload locally as fallback.

## Local Deployment Shape

Target user story:

- A family user downloads Coval HeYi, runs it on a home computer, and chooses one model backend:
  - local model + LoRA adapter;
  - local smaller model for smoke mode;
  - remote API provider;
  - future NAS/home-server mode.

Recommended package:

- `docker compose up` starts:
  - Next.js web app;
  - FastAPI API;
  - SQLite volume for family timeline;
  - optional worker for OCR/ASR/weekly reports.
- Keep model weights outside the image in a mounted volume.
- Keep private family data in a local mounted volume, never in the image.

Suggested services:

- `web`: Next.js app.
- `api`: FastAPI app with provider abstraction.
- `worker`: scheduled jobs for reminders, weekly reports, OCR/ASR queues.
- `db`: SQLite file volume first; optional Postgres later for multi-user deployments.

## Memory And Data Layer

Default local memory:

- SQLite for reports, symptoms, medications, labs, appointments, safety events, and weekly summaries.
- File storage folder for OCR source images/audio if the user opts in.
- All rows should carry provenance: source type, source filename/id, timestamp, model version, and user-confirmed status.

AI memory boundary:

- Use structured SQL memory for counting, trends, reminders, and doctor summaries.
- Use RAG later for cited public medical resources, not for private family facts unless the user opts into a local-only vector index.

## Scheduled Jobs

Useful first cron-style jobs:

- Daily blood pressure reminder for a selected family member.
- Weekly family health digest:
  - new records this week;
  - missing fields;
  - medication/refill reminders;
  - abnormal lab flags already present in uploaded reports;
  - appointments and follow-up checklist.
- Monthly export backup prompt.

Implementation:

- Local Docker: APScheduler or Celery beat inside `worker`.
- Desktop-only simple mode: FastAPI background scheduler.
- Cloud/self-hosted mode: cron-compatible worker container.

## OCR And ASR Adaptation

OCR intake:

- Accept phone photos, PDF reports, and pasted report text.
- Normalize output into the same structuring API contract.
- Keep image/PDF provenance linked to extracted fields.
- First implementation can use pluggable providers:
  - local OCR engine for private mode;
  - cloud OCR only if the user explicitly configures it.

ASR intake:

- Voice note -> transcript -> medical structuring.
- Store transcript plus confidence/provenance.
- Add a family-user correction loop before saving to timeline.

Clinic-inspired integration pattern:

- Treat OCR/ASR as async ingestion jobs with visible status:
  - uploaded;
  - extracted;
  - needs review;
  - saved.
- Never silently save uncertain extracted medical facts without user review.

## Product Roadmap

Near term:

- Polish the family dashboard and mobile recording flow.
- Prepare gated HF adapter/model card.
- Add Docker Compose skeleton.
- Add local SQLite schema and API routes for real CRUD over synthetic examples.

Medium term:

- Provider abstraction: local model, HF adapter, OpenAI-compatible API.
- OCR/ASR job queue with review states.
- Weekly report worker.
- Local encrypted backup/export.

Long term:

- Optional mobile app shell.
- Local vector index for private notes only if user opts in.
- Family sharing with role-based access.
