# Coval HeYi: Family Health Memory Copilot

Coval HeYi is a private-first Chinese family health memory copilot prototype. This public build is synthetic/public-safe only: it turns fictional health notes and blood-pressure/symptom updates into reviewable structured records, doctor-facing summaries, and safety prompts. OCR/ASR, reminders, and weekly reports remain planned product stages.

It is not a diagnosis or medication-advice system. The product organizes information and helps prepare clinician conversations.

![Coval HeYi desktop review sheet](docs/assets/coval-heyi-desktop.png)

![Coval HeYi mobile record screen](docs/assets/coval-heyi-mobile.png)

## What This Project Shows

- A product story grounded in the author's earlier Coval AI memo work, clinic/Phlox workflow thinking for doctor-facing services, and a family need: keeping up with frequent checkups, reports, medication notes, and daily blood-pressure records at home.
- A migration-backed local product spine for synthetic family health memory: capture-first immutable source evidence, leased failure recovery, candidate review, server-confirmed save, append-only versions, timeline reload, safety evidence, and undo.
- An OCR/ASR intake design for the future software service; the current UI exposes labeled stubs and does not process files or audio.
- An evaluation-first LoRA workflow for Chinese medical-record structuring; QLoRA remains a planned option, not a completed training claim.
- Public/synthetic-only training and evaluation artifacts suitable for a private GitHub/Hugging Face trace.
- A measured model story: the v2 adapter is integrated but deployment-blocked; SFT v3 and a Phase 2b prompt candidate were evaluated and rejected. The product default remains `mock-rules-v2` plus deterministic safety controls.

## Product Origin

Coval began as an AI memory product: collect fragmented context, preserve useful personal history, and turn it into timely briefings. Coval HeYi applies that memory pattern to family health.

The product direction also borrows discipline from clinic/Phlox work: healthcare AI should be a reviewable workflow, not a loose chatbot. The useful loop is capture -> structure -> verify -> save -> summarize for the next care conversation.

The future family-facing motivation is practical. A parent who often goes for checkups may accumulate lab reports, appointment notes, medication changes, and daily blood-pressure readings faster than the family can organize them. The intended product direction is a local home-running memory layer, but this build must not receive real family or patient data until every threat-model gate passes.

## Current UI

The web UI is a Next.js app under `apps/coval-health-web`.

- Desktop: a one-viewport family health workbench with record intake, smart organization, family review confirmation, doctor-facing summary, missing-info checklist, visit-prep checklist, safety boundary, and compact project evidence.
- Mobile: an iOS-like `New Record` page that opens directly on the recording workflow, with member selection, OCR/voice/blood-pressure modes, source/date/missing-field context, smart organization, and save-after-review state.
- The UI accepts arbitrary editable fictional notes, members, dates, and source labels and calls the local FastAPI/SQLite service for the implemented synthetic workflow: persist source -> organize/recover -> edit/review -> approve -> versioned timeline -> undo.
- Failed local-model work remains visible in a recovery inbox. Atomic leases prevent concurrent retries from both becoming canonical memory, and rejection invalidates late model output.
- API/database/provider states are visible. If the API is offline, writes are disabled rather than silently falling back to an in-memory success state.
- Demo-only hooks such as local OCR/PDF intake are clearly labeled and do not read real files in the public example.
- Screenshots in `docs/assets/` are browser captures regenerated on 2026-08-28 from the tested desktop and mobile flows.

## OCR And ASR Service Design

OCR and ASR are part of the software-service design, but the current public demo uses synthetic text and demo stubs rather than real family files.

Planned local-first flow:

1. OCR intake: phone report photo, PDF, or pasted OCR text. In the public web demo this appears as a local-intake hook, not a real file upload.
2. ASR intake: family voice note or symptom description -> transcript.
3. Structuring: the same medical schema handles OCR text, ASR transcript, manual notes, medication records, and blood-pressure entries.
4. Review: uncertain facts become family-verifiable rows with explicit `核对` / `补充` states and are not silently saved.
5. Timeline: user-confirmed records enter the local family memory database.
6. Weekly report: a worker can summarize new records, missing fields, reminders, and doctor-prep questions.

Production implementation should prefer local OCR/ASR engines for private mode, with cloud providers only if explicitly configured by the user.

## Safety And Privacy Boundary

- Public artifacts use only public or synthetic data.
- Real family medical data must not enter Git, Hugging Face, logs, cloud services, Narval jobs, or training data.
- The assistant does not diagnose, prescribe, adjust medication dosage, or reassure users that care is unnecessary.
- Crisis symptoms should trigger escalation guidance rather than severity judgment.
- `COVAL_REAL_DATA_MODE=1` is an explicit opt-in fail-closed sentinel. It cannot determine whether pasted content is real; the UI therefore requires synthetic-only acknowledgement. Real use remains blocked on full-database/WAL encryption, OS key custody and recovery, authentication, encrypted backup, verified purge, and a fixed/pinned SQLite Windows package.

See [the architecture](docs/ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md),
[claim ledger](docs/CLAIM_LEDGER.md), and [90-second demo](docs/DEMO_90S.md).

## Local Web Demo

Install once:

```powershell
cd <repo-root>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd apps\coval-health-web
npm.cmd ci
```

Start the API in terminal 1:

```powershell
cd <repo-root>
.\.venv\Scripts\python.exe -m uvicorn src.serve.coval_health_api:app --host 127.0.0.1 --port 8000
```

Start the web app in terminal 2:

```powershell
cd <repo-root>\apps\coval-health-web
npm.cmd run dev
```

Open `http://127.0.0.1:3000`. The frontend may retain packaged research-evidence
text while offline, but it shows the failure and disables every durable write.
The default development database is `data/local/coval_health.sqlite` and is
ignored by Git; set `COVAL_DATA_DIR` or `COVAL_HEALTH_DB_PATH` to override it.

## Portable Vault Backup And FHIR Export

The vault CLI works without a model. It creates a consistent SQLite snapshot,
adds a SHA-256/byte-count manifest and one FHIR R4 document Bundle per family
member, verifies the package, and restores only into a clean database path:

```powershell
cd <repo-root>
.\.venv\Scripts\python.exe scripts\manage_vault.py backup `
  --database data\local\coval_health.sqlite `
  --output backups\synthetic-demo.coval `
  --acknowledge-synthetic-only-unencrypted
.\.venv\Scripts\python.exe scripts\manage_vault.py verify `
  --archive backups\synthetic-demo.coval
.\.venv\Scripts\python.exe scripts\manage_vault.py restore `
  --archive backups\synthetic-demo.coval `
  --database <clean-synthetic-restore-path>\coval_health.sqlite `
  --acknowledge-synthetic-only-unencrypted
```

The v1 archive is intentionally marked `encryption: none` and every writing CLI
requires an explicit synthetic-only acknowledgement. It is a tested portability/
recovery foundation for demo data only. Even if the storage location is separately
encrypted, this build and vault v1 remain prohibited for real family/patient data
until every threat-model gate passes.

## Key Engineering Decisions

- [ADR 0001](docs/adr/0001-capture-first-leased-processing.md): persist source before inference; run the provider outside the SQLite write transaction; attach only with a live lease token.
- [ADR 0002](docs/adr/0002-review-before-canonical-memory.md): machine candidates never enter the timeline without review; edits and undo append versions.
- [ADR 0003](docs/adr/0003-model-gates-over-model-optimism.md): a connected model is not promoted when frozen safety/comparator gates fail.
- [ADR 0004](docs/adr/0004-vault-v1-is-portability-not-privacy.md): tested recovery is kept separate from encryption/authenticity claims.

## Validation

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File scripts\run_local_quality.ps1
```

Use `-Install` to install dependencies and `-SkipBrowser` to omit Playwright.
The standard entry runs policy checks, backend/API/process-restart tests,
frontend lint/typecheck/build, and browser E2E. The longer research smoke suite is:

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1
```

The optional model runtime is isolated from the lightweight web/test environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_local_model_runtime.ps1
$env:COVAL_MODEL_PROVIDER = "transformers_adapter"
$env:COVAL_MODEL_BASE_PATH = "<local-model-path>"
$env:COVAL_MODEL_ADAPTER_PATH = "<local-adapter-path>"
$env:COVAL_TRANSFORMERS_LOAD_IN_4BIT = "true"
```

Model providers require explicit local paths, force Hugging Face offline mode,
and never fall back silently to mock. `scripts/benchmark_local_provider.py`
adds a non-loopback socket guard for the fixed synthetic latency/quality run.
An arbitrary local path is deliberately recorded as identity-unverified; it is
not labeled as the historical v2 candidate until a pinned full-file identity
manifest exists. Historical v2 identity and measurements live only in the
curated public evidence summary.
`transformers_base` is an adapter-off causal benchmark only;
`scripts/compare_local_inference.py` compares it with mock, local v2, and the
recorded historical v2 metrics.

## Model And Eval Status

Historical evidence-backed candidate:

```text
Qwen/Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary template
```

Production-equivalent local NF4 regression results (`n=10`, `n=4`, and `n=6`
respectively; development slices, not an independent test set or clinical validation):

| Slice | Base NF4 F1 | Adapter NF4 F1 | Adapter - base |
| --- | ---: | ---: | ---: |
| synthetic_v0 | 0.6767 | 0.6767 | 0.0000 |
| medication_contrast_v0 | 0.6897 | 0.6897 | 0.0000 |
| safety_onset_edge_v1_1 | 0.6939 | 0.6222 | -0.0717 |

On the separate 24-row blind confirmation set, both old-prompt arms refused 8
of 16 non-refusal cases (50% false refusal). The adapter also falsely refused
1/5 safe adversarial cases. These product-context results do not establish
adapter superiority and block deployment.

Decision: **BLOCKED**. Earlier `0.7656 / 0.9032 / 0.8261` values came from
context-contaminated development prompts containing semantic eval IDs and
gold-like input types. They remain documented as a correction, not as headline
quality evidence.

SFT v3 was trained and evaluated, but it is not the default candidate. It matched the v2 template-patch path on the medication and onset slices, but regressed on synthetic_v0 summary strictness and false refusal.

See:

- `docs/CURRENT_STATE.md`
- `docs/DURABLE_PRODUCT_SPINE.md`
- `docs/PRODUCTIZATION_ROADMAP_2026_08.md`
- `docs/PHASE_0_1_INTERNAL_REVIEW.md`
- `docs/PHASE_2_LOCAL_INFERENCE.md`
- `docs/INSPIRATION_AND_LICENSES.md`
- `docs/experiment_log.md`
- `docs/error_analysis.md`
- `docs/INTERVIEW_DEFENSE.md`
- `docs/PHASE_2_LOCAL_INFERENCE.md`
- `docs/PHASE_2B_SAFETY_INTENT.md`
- `artifacts/public/phase2_local_inference/evidence_summary.json`
- `artifacts/public/phase2b_safety_intent/evidence_summary.json`

## Honest Current Scope

This repo is intentionally framed as an evaluation-first product prototype, not a production medical agent.

- The LoRA experiment is a failure-driven small-sample SFT. `sft_v2` has 26 synthetic hand-authored rows: 20 train and 6 validation, and the run completed only 3 optimization steps. Production-equivalent local evaluation did not establish adapter superiority and exposed false-refusal regressions, so the candidate was not promoted.
- The local product layer is a Next.js/FastAPI/SQLite prototype over synthetic examples. Its durable path now has migrations, capture-before-inference, retry leases, immutable sources, candidate approval, versions, idempotency, audit/safety evidence, process-restart recovery, and browser-tested undo.
- The default structuring provider is still `mock-rules-v2`. The API now has
  explicit `transformers_base`, `transformers_adapter`, and `llama_cpp`
  boundaries. Real local v2 NF4 inference and browser/SQLite E2E are connected
  and measured. The frozen same-local unquantized comparator does not fit this
  GPU, so that quantization gate is not evaluable; false refusals and
  descriptive historical gaps block deployment, and the candidate is therefore
  not the default. Real OCR/ASR,
  reminder workers, daily check-ins, weekly reports, PDFs, and encrypted backups
  are not implemented. A checksum-verified **unencrypted** local vault backup,
  clean-path restore, and FHIR R4 export are implemented and regression-tested.
- It is not yet a complete RAG agent. Phase 6 has started with a retrieval-first smoke harness over a tiny synthetic/public-safe corpus: 7 source snippets, 8 labeled queries, Recall@1/3 and MRR, plus no-answer calibration.
- It is not yet a llama.cpp/GGUF local-inference deployment. The Transformers/PEFT NF4 path is real; the GGUF boundary remains unexecuted.

Safe resume wording after clean-clone CI passes: `Built a synthetic-only local family-health memory platform with immutable source provenance, capture-first failure recovery, review-before-save, append-only versions, tested backup/restore, deterministic safety controls, conservative FHIR R4 mapping, and model gates that rejected unsafe candidates.`

Avoid overclaiming: do not describe the current project as a large-scale medical dataset, a deployed clinical decision system, a production RAG agent, or a completed GGUF/llama.cpp local runtime.

## Phase 6 RAG Status

Phase 6 follows the same lesson as the earlier rageval work: retrieval quality is measured before generation is trusted.

Current scaffold:

- Corpus: `data/public/rag_v0/corpus.jsonl`
- Gold queries: `eval/rag/gold_v0.jsonl`
- Runner: `scripts/run_rag_retrieval_eval.py`
- Metrics: `results/rag_v0/metrics.json`

Current smoke result on the tiny bilingual representation set:

| Metric | Value |
| --- | ---: |
| Corpus size | 7 |
| Query count | 8 |
| Recall@1 | 1.0000 |
| Recall@3 | 1.0000 |
| MRR | 1.0000 |
| No-answer accuracy | 1.0000 |

These numbers are only a scaffold sanity check. The next real RAG work is to expand public-resource evidence, add harder held-out queries, compare lexical/dense/hybrid retrieval, and then evaluate citation faithfulness and unsupported claims.

## Hugging Face Upload Flow

Do not paste or commit tokens. Log in interactively.

Local CLI check:

```powershell
cd <repo-root>
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
- `src/serve/coval_health_api.py` - compatibility entrypoint for the durable local API.
- `src/serve/memory_api.py` - persistent health-memory routes and contracts.
- `src/health_memory/` - migrations, SQLite invariants, versions, idempotency, and projections.
- `src/product_spine.py` - replace-on-run synthetic evaluation smoke tool, not canonical product storage.
- `eval/` - gold sets and metrics.
- `train/` - SFT dataset builders and training entry points.
- `scripts/` - Narval, Hugging Face, eval, and workflow utilities.
- `docs/` - plan, packaging notes, experiment log, and error analysis.

## Project Positioning

This is one project with two faces:

1. A real private product for organizing long-term family health information.
2. A portfolio-grade LoRA evaluation project with concrete metrics, leakage correction, failure analysis, and model-rejection decisions.

The research contribution is not a generic chatbot. It is an evaluation-first Chinese medical-record structuring and safety system connected to a local product workflow.
