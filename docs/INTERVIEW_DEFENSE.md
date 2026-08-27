# Coval HeYi Interview Defense

This note is the concise version to use for interviews, project writeups, and demo walkthroughs. It keeps the project impressive without overclaiming.

## One-Line Positioning

Coval HeYi is an evaluation-first Chinese family health memory copilot: it stores reviewable health memory locally, prepares doctor-facing summaries, and keeps a deterministic product path working even when a connected Qwen2.5-7B LoRA research candidate fails its deployment gate.

## Product Origin

Coval started from an AI memo idea: capture fragmented context, preserve useful memory, and turn it into timely briefings. Coval HeYi applies that pattern to family health.

The healthcare direction also borrows from clinic/Phlox thinking: a useful medical AI workflow should be reviewable and evidence-aware, not an open-ended diagnosis chatbot.

The family use case is practical: a parent who often has checkups, lab reports, medications, symptoms, and daily blood-pressure readings needs a private home system that keeps records organized and ready for a doctor visit.

## What Is Complete Today

- A synthetic/public-safe evaluation harness for Chinese medical structuring, safety refusal, crisis escalation, summary faithfulness, and hallucination checks.
- A measured historical model candidate: `Qwen/Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary template`. It is integrated but deployment-blocked; `mock-rules-v2` remains the product default.
- A local Next.js/FastAPI demo that shows record intake, structured review, family timeline, doctor summary, safety state, completeness, model evidence, blood-pressure entry, and weekly-report hooks.
- OCR and ASR appear as clearly labeled future intake adapters. The public demo accepts synthetic pasted text and manual blood-pressure notes; it does not run an OCR or ASR engine.
- A synthetic/public-safe adapter packaging and upload path; public claims rely on committed evidence summaries rather than access to private weights.
- A Phase 6 retrieval-first RAG scaffold with a tiny bilingual corpus and labeled query set.

## What Not To Claim

- Do not call this a production clinical decision system.
- Do not claim diagnosis, prescription, medication adjustment, or reassurance that care is unnecessary.
- Do not call the current system a complete RAG agent. Phase 6 currently has retrieval metrics only.
- Do not claim completed llama.cpp/GGUF local inference. That is a feasible packaging target, not an implemented deployment.
- Do not imply the SFT data is large. `sft_v2` has 26 hand-authored synthetic examples: 20 train and 6 validation. The story is failure-driven data quality and evaluation discipline, not scale.

## Demo Walkthrough

1. Open the web demo and start from `New Record`.
2. Show manual text and blood-pressure logging, then point out that OCR and voice are visibly disabled/labeled stubs.
3. Pick a synthetic sample and point out the review table: structured fields remain editable before entering memory.
4. Show the safety block: crisis symptoms escalate; medication dosage changes are refused.
5. Show the AI memo lineage: capture -> review -> memory -> doctor briefing.
6. Show the model evidence table and explain that metrics are from synthetic/public-safe evals.
7. End with the timeline and weekly report entry points: this is a home health memory product, not only a model demo.

## Interview Answers

**How much data did you train on?**

The v2 headline result is a small failure-driven SFT: 26 synthetic hand-authored rows, 20 train and 6 validation. I keep that transparent. The contribution is the evaluation loop, targeted failure fixing, and product integration rather than dataset scale.

**Why is the F1 jump meaningful if the dataset is small?**

It is meaningful inside a controlled harness because the same eval contract measures baseline and adapter behavior. I would not present it as population-level medical generalization. I present it as evidence that the system can identify a blocker, add focused data, rerun the harness, and reject regressions.

**Is this RAG?**

Not yet as a full agent. Structured patient memory is SQL-like state. RAG is planned for cited explanations over public resources. Phase 6 currently validates retrieval metrics, no-answer behavior, and the evaluation path before generation.

**Where do OCR and ASR fit?**

OCR and ASR are intake adapters. A report photo, PDF OCR text, or family voice note becomes reviewable text, then passes through the same medical structuring and safety contract. The public demo uses synthetic text stubs to avoid real family data.

**What makes this safe for a portfolio?**

The repo separates real family motivation from public artifacts. Public code, evals, docs, and screenshots use synthetic/public-safe data only. Real medical records, local databases, tokens, checkpoints, and private scans are not committed or uploaded.

**Why use a lease and CAS instead of holding a database transaction during inference?**

Model latency is unpredictable, so holding SQLite's writer lock would serialize unrelated work and make crashes harder to recover. The source is committed first; a short atomic claim issues an expiring token; inference runs outside the transaction; only the still-current token may attach a candidate. Candidate and version CAS then reject stale human edits.

**Why was the LoRA candidate not promoted?**

After removing semantic eval IDs and gold-like input types, the production-context old-prompt base/adapter F1 was `0.6767/0.6767`, `0.6897/0.6897`, and `0.6939/0.6222` across the three development slices. Both arms falsely refused 8/16 non-refusal cases on the blind confirmation set; the adapter also falsely refused 1/5 safe adversarial cases. The same-local unquantized comparator was not evaluable on the available GPU. Availability was proven; promotion was not justified.

**How do you prevent a random local adapter from being recorded as the accepted v2?**

The runtime now labels arbitrary local paths as identity-unverified and uses a generic extraction version. Historical v2 measurements remain a separate curated receipt. Promotion to a named artifact requires a future pinned manifest covering base revision and full-file hashes; an environment path alone is not identity evidence.

**Why can two identical notes become two records?**

Content equality is not provenance equality. SQLite v8 deduplicates identical member/kind/date/content only within the same declared source label, so two distinct report sources are retained as separate immutable evidence. A fuller content-blob/capture-event split is a future normalization, not a hidden current claim.

## What Changed Since The First Demo

Next.js now writes through FastAPI/SQLite; source evidence is committed before
inference; failed processing survives reload behind an expiring lease; candidate
and version CAS reject stale review; undo appends history; process restart,
Playwright, vault restore and optional local-adapter paths are tested. The model
was connected and measured, but the evidence gate did not promote it.

The next high-leverage work is security rather than another model sweep:
SQLCipher with a fixed SQLite runtime, DPAPI plus independent recovery, local
authentication, encrypted backup v2, verified purge, and a signed clean-VM
Windows package. OCR/ASR, notifications and expanded retrieval follow that gate.

## Safe Resume Wording

Built a synthetic-only local family-health memory platform with capture-first immutable source evidence, leased failure recovery, review-before-save, append-only versions, tested backup/restore, deterministic safety controls, conservative FHIR R4 mapping, and model gates that rejected unsafe candidates.
