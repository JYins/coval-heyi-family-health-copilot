# Project Plan

## Phase 0 - Initialization And Safety Fence

Status: scaffold complete; keep privacy checks active.

- Create repo skeleton, `AGENTS.md`, `.gitignore`, `.env.example`, and Narval isolation docs.
- Keep only non-secret server metadata in docs.
- Verify Narval connectivity only with read-only checks; do not touch `/home/syin94/scratch/MEng_Project`.
- Initialize Git after privacy rules are in place.

Exit criteria:

- Repo has safety-first docs and ignored private paths.
- No passwords, MFA codes, tokens, private records, or thesis data are present.

## Phase 1 - Gold Eval Set First

Goal: create the measurement layer before training.

Status: initial synthetic eval is complete, with an added medication-safety contrast set.

Tasks:

- Create 5-10 synthetic Chinese report/symptom examples under `eval/gold/`.
- Keep targeted contrast sets separate from `synthetic_v0` when they would break older baseline reproducibility.
- For each example, write target structured JSON, target doctor-facing summary, and safety/crisis labels.
- Implement metric skeletons:
  - field-level extraction F1;
  - strict summary coverage, relaxed diagnostic summary coverage, and unsupported claim checks;
  - safety refusal rate;
  - crisis escalation recall;
  - hallucination and overdiagnosis checks.
- Record dataset version and known limitations in `docs/experiment_log.md`.

Exit criteria:

- `eval/run_eval.py` can run on fixture outputs and produce a JSON metrics file.
- Missing metrics fail loudly instead of silently passing.
- Medication documentation versus medication-dose adjustment contrast cases pass fixture checks.

## Phase 2 - Baseline Model Evaluation

Goal: measure the un-tuned base model before changing it.

Tasks:

- Select a base model, likely `Qwen/Qwen2.5-7B-Instruct` or a smaller local stand-in for smoke tests.
- Run all Phase 1 metrics on the gold set.
- Log exact model ID, prompt version, decoding settings, hardware, runtime, and outputs.
- Inspect failures and update `docs/error_analysis.md`.

Exit criteria:

- Baseline metrics are recorded with result file paths.
- At least 5 representative failure examples are categorized.

## Phase 3 - Local Product Spine

Goal: make the product workflow real on fake data before Narval training.

Status: in progress. The first SQLite smoke spine runs on `synthetic_v0` fixture
predictions and writes `results/product_spine/synthetic_v0_report.json`.

Tasks:

- Build a local skeleton: OCR/ASR stub -> structuring -> SQLite timeline -> summary -> safety escalation.
- Use only fake/synthetic examples.
- Add a minimal local interface or CLI for end-to-end smoke tests.
- Write schema notes for reports, lab items, medications, symptom logs, appointments, and reminders.

Exit criteria:

- 2-3 fake reports can flow through the full pipeline.
- The output includes a timeline and doctor-facing summary.

## Go/No-Go Gate Before Fine-Tuning

Proceed to Narval LoRA/QLoRA only if:

- The gold set is coherent enough to expose baseline failures.
- Baseline metrics are reproducible.
- The product spine runs end-to-end on fake/public data.
- Privacy rules are still intact.
- The user approves moving to remote training.

## Phase 4 - Product-First A100 Fine-Tuning On Narval

Goal: use the A100 to produce one measurable adapter that makes the product spine more useful, not to sweep a large matrix before the product works. Every experiment still uses public/synthetic data only and is judged by the Phase 1-3 eval harness.

Remote isolation:

- Remote root: `/home/syin94/scratch/lora_health`.
- Never use `/home/syin94/scratch/MEng_Project` for this repo.
- Job names start with `lora_health_`.
- Use a separate venv and output directory.

Primary training ladder:

- 7B baseline: run the base instruct model through the eval harness and the local fake-data product spine.
- 7B QLoRA/LoRA SFT main run: train one adapter focused on the biggest product blocker, likely Chinese report/symptom structuring plus safety refusal. Start with rank 16 unless baseline failures suggest underfitting or overfitting.
- Product integration check: load the adapter into the local pipeline and verify that fake reports flow through OCR/ASR stub -> structure -> timeline -> doctor summary -> safety escalation better than baseline.
- Targeted second run only if the first adapter exposes a clear problem:
  - add failure-driven data if recurring extraction or safety examples fail;
  - add structured JSON constrained decoding if JSON validity blocks ingestion;
  - try rank 8 or 32 only if rank 16 clearly underfits, overfits, or is too heavy;
  - try a 5k dataset after a 1k smoke run only if the data quality is coherent;
  - try 20k or 14B QLoRA only after the 7B adapter already improves product metrics and the remaining bottleneck plausibly needs scale.

Deferred research backlog:

- LoRA rank matrix: 8 / 16 / 32.
- Dataset-size matrix: 1k / 5k / 20k.
- Data-mix matrix: extraction-only vs extraction+safety vs extraction+summary mixed SFT.
- Model-size comparison: 7B QLoRA vs 14B QLoRA.
- Safety preference alignment: DPO/ORPO only after there is a real chosen/rejected preference set from safety failures.

Complexity rule:

- The first remote milestone is a usable adapter, not a complete ablation table.
- Add complexity only when it answers a product or eval failure that has been observed.
- Do not run full fine-tuning unless a later review explicitly justifies it. Adapter-based methods remain the default because they are reproducible, cheaper to share, and safer for HF release.

Tracking requirements:

- Track adaptation type, base model size, LoRA rank, quantization mode, data mix, dataset version, dataset size, LR, batch size, sequence length, GPU, queue/runtime, final loss, output directory, exact eval result path, and product-spine smoke result.
- Record why each experiment exists. A run with no research question should not be submitted.

Exit criteria:

- Before/after eval deltas are recorded.
- At least one adapter improves extraction, safety, crisis recall, or summary faithfulness over the 7B baseline.
- The improved adapter can be used by the local product spine on fake/public examples.
- Failure analysis explains what improved, what regressed, and which next experiment follows from the evidence.

## Phase 5 - Focused Ablations And Failure-Driven Improvements

Run only after the Phase 4 adapter is useful enough to plug into the product spine.

Candidates:

- LoRA rank ablation: 8 / 16 / 32 under the same dataset and prompt version.
- Dataset-size ablation: 1k / 5k / 20k under the same model and data mix.
- Data-mix ablation: extraction-only vs extraction+safety vs extraction+summary mixed SFT.
- Decoding ablation: prompted JSON vs structured constrained JSON decoding.
- Model-size ablation: 7B QLoRA vs 14B QLoRA if compute allows.
- Alignment ablation: SFT vs safety-focused DPO/ORPO only if refusal, crisis escalation, or medication-advice failures justify it.

Exit criteria:

- The project can explain which factor mattered: model size, adapter rank, data volume, data mix, decoding control, or safety alignment.
- Negative results are logged as useful evidence, not hidden.
- No ablation blocks product integration work.

## Phase 6 - RAG Extension

Use the existing rageval lesson: retrieval evaluation first, generation second.

Status: scaffold started. The first `rag_v0` retrieval smoke uses a tiny synthetic/public-safe bilingual corpus and a labeled query set to validate the metric contract before any generation layer.

Planned metrics:

- Recall@K and MRR for evidence retrieval.
- Citation faithfulness.
- Unsupported-claim rate.
- No-answer calibration.

Design principle:

- Structured health memory stays in SQL.
- RAG is for cited explanations over public resources, not for counting a patient’s historical lab tests.

Current artifacts:

- Corpus: `data/public/rag_v0/corpus.jsonl`
- Gold queries: `eval/rag/gold_v0.jsonl`
- Runner: `scripts/run_rag_retrieval_eval.py`
- Metrics: `results/rag_v0/metrics.json`

Current limitations:

- `rag_v0` has only 7 source snippets and 8 labeled queries, so the perfect smoke metrics are not a production claim.
- No generation, citation-faithfulness scoring, dense embedding comparison, hybrid retrieval, or llama.cpp/GGUF local serving is complete yet.
- The next step is to expand public-resource evidence and held-out queries before adding answer generation.
