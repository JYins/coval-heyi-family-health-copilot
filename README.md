# Coval HeYi: Family Health Memory Copilot

Coval HeYi is a private-first Chinese family health memory copilot. It turns messy family health notes, OCR report text, medication records, and symptom logs into structured records, doctor-facing summaries, safety prompts, reminders, and weekly family updates.

It is not a diagnosis or medication-advice system. The product organizes information and helps prepare clinician conversations.

![Coval HeYi desktop review sheet](docs/assets/coval-heyi-desktop.png)

![Coval HeYi mobile record screen](docs/assets/coval-heyi-mobile.png)

## What This Project Shows

- A local product spine for family health memory: record capture, structuring, timeline, doctor summary, safety boundary, daily blood-pressure entry, and weekly report entry.
- An evaluation-first LoRA/QLoRA workflow for Chinese medical-record structuring.
- Public/synthetic-only training and evaluation artifacts suitable for a private GitHub/Hugging Face trace.
- A measured model story: SFT v2 plus deterministic summary rendering is the current default; SFT v3 was completed as an ablation and rejected because it did not improve the default candidate.

## Current UI

The web UI is a Next.js app under `apps/coval-health-web`.

- Desktop: a clinic-style review sheet that fits in one viewport, with record input, structured review rows, safety boundary, doctor summary, completeness, and model evidence.
- Mobile: an iOS-like record page that opens directly on `New Record`, with OCR text, voice transcription, blood-pressure entry, smart organization, and structured preview.

## Safety And Privacy Boundary

- Public artifacts use only public or synthetic data.
- Real family medical data must not enter Git, Hugging Face, logs, cloud services, Narval jobs, or training data.
- The assistant does not diagnose, prescribe, adjust medication dosage, or reassure users that care is unnecessary.
- Crisis symptoms should trigger escalation guidance rather than severity judgment.

## Local Web Demo

```powershell
cd D:\lora\apps\coval-health-web
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

Optional API evidence endpoint:

```powershell
cd D:\lora
.\.venv\Scripts\python.exe -m uvicorn src.serve.coval_health_api:app --host 127.0.0.1 --port 8000
```

The frontend falls back to static synthetic evidence if the API is not running.

## Validation

```powershell
cd D:\lora\apps\coval-health-web
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Full project smoke checks:

```powershell
cd D:\lora
powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1
```

## Model And Eval Status

Current default candidate:

```text
Qwen/Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary template
```

Current public/synthetic eval highlights:

| Slice | Extraction F1 | Relaxed summary | Safety refusal | Crisis recall |
| --- | ---: | ---: | ---: | ---: |
| synthetic_v0 | 0.7656 | 0.8108 | 100% | 100% |
| medication_contrast_v0 | 0.9032 | 0.9444 | 100% | n/a |
| safety_onset_edge_v1_1 | 0.8261 | 0.9474 | 100% | 100% |

SFT v3 was trained and evaluated, but it is not the default candidate. It matched the v2 template-patch path on the medication and onset slices, but regressed on synthetic_v0 summary strictness and false refusal.

See:

- `docs/experiment_log.md`
- `docs/error_analysis.md`
- `results/sft_v2_eval_template_patch/comparison.md`
- `results/sft_v3_eval/comparison_vs_v2_template_patch.md`

## Hugging Face Upload Flow

Do not paste or commit tokens. Log in interactively.

Local CLI check:

```powershell
cd D:\lora
powershell -ExecutionPolicy Bypass -File scripts\hf_local_login.ps1
powershell -ExecutionPolicy Bypass -File scripts\hf_local_login.ps1 -WhoamiOnly
```

Adapter upload should be run where the adapter files exist. On Narval, after opening the WSL SSH ControlMaster session:

```bash
cd /home/syin94/scratch/lora_health/code
source /home/syin94/scratch/lora_health/venv/bin/activate
hf auth login
export HF_REPO_ID="Jeremyyy1225/coval-heyi-qwen2p5-7b-lora-v2"
bash scripts/prepare_hf_adapter_upload.sh
```

Recommended initial visibility:

```text
GitHub: private
Hugging Face: private or gated
License: no open-source license yet
```

This creates a public/private trace without granting automatic reuse rights before the project packaging is mature.

## GitHub Packaging Notes

Before pushing:

- Keep `.env`, tokens, private keys, real family records, local databases, checkpoints, and adapter weights out of Git.
- Commit source code, configs, docs, synthetic/public eval fixtures, small reproducibility manifests, and UI screenshots under `docs/assets`.
- Do not commit `data/private/`, `*.real.*`, `*.pii.*`, `graphify-out/`, `node_modules/`, `.next/`, or model weight files.

Suggested pre-push checks:

```powershell
git status --short
powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1
cd apps\coval-health-web
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

## Repository Map

- `apps/coval-health-web` - Next.js family-facing web UI.
- `src/serve/coval_health_api.py` - local FastAPI evidence/demo API.
- `src/product_spine.py` - synthetic-data product spine.
- `eval/` - gold sets and metrics.
- `train/` - SFT dataset builders and training entry points.
- `scripts/` - Narval, Hugging Face, eval, and workflow utilities.
- `docs/` - plan, packaging notes, experiment log, and error analysis.

## Project Positioning

This is one project with two faces:

1. A real private product for organizing long-term family health information.
2. A portfolio-grade LoRA/QLoRA evaluation project with concrete metrics, failure analysis, and ablation decisions.

The research contribution is not a generic chatbot. It is an evaluation-first Chinese medical-record structuring and safety system connected to a local product workflow.
