# Model Card Draft: med-structurer-zh

Status: draft; Qwen2.5-7B LoRA SFT v1-v3 experiments have run on synthetic data.
The historical research candidate is SFT v2 plus deterministic summary
rendering; v3 was evaluated and rejected. The durable local web product uses an
explicitly labeled deterministic mock by default. A local NF4 v2 adapter provider
has been connected and browser/SQLite-tested, but remains opt-in and deployment-
blocked by the frozen safety/comparator gates.

## Intended Use

Structure Chinese health reports, symptom notes, and medication/reminder information into a longitudinal health record, then generate clinician-facing summaries and family update drafts.

## Out Of Scope

- Diagnosis.
- Medication dosage advice or adjustment.
- Reassurance that medical care is unnecessary.
- Emergency triage beyond conservative escalation guidance.

## Training Data

The current SFT v2 dataset contains 26 synthetic rows (20 train / 6 validation).
Only public or synthetic data is allowed for train/eval artifacts that may be
published. No real family records were used.

## Evaluation

Implemented metrics:

- Field-level extraction F1.
- Summary coverage and unsupported-claim rate.
- Safety refusal rate.
- Crisis escalation recall.
- Hallucination and overdiagnosis rates.

The earlier `0.7656` development result is context-contaminated because its prompt
included semantic eval IDs and gold-like input types. In the production-context
rerun, old-prompt base/adapter F1 was `0.6767/0.6767`, `0.6897/0.6897`, and
`0.6939/0.6222`. Both arms falsely refused 8/16 non-refusal cases on the blind
confirmation set, and the adapter falsely refused 1/5 safe adversarial cases.
The adapter therefore remains blocked.
See `docs/PHASE_2_LOCAL_INFERENCE.md` and `docs/error_analysis.md`.

RAG groundedness and citation faithfulness remain planned after the retrieval
scaffold is expanded.

## Limitations

This system is an information organization assistant, not a clinician. The
dataset is tiny and synthetic, and the product default is a deterministic path
rather than the adapter. Outputs must be reviewed before entering canonical memory and by a
qualified medical professional when used for care communication.
