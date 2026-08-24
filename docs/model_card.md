# Model Card Draft: med-structurer-zh

Status: draft; Qwen2.5-7B LoRA SFT v1-v3 experiments have run on synthetic data.
The evidence-backed research candidate is SFT v2 plus deterministic summary
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

The end-to-end core-field F1 history is `0.0303 -> 0.6087 -> 0.7656`; this is a
combined contract/normalization/LoRA story, not a LoRA-only delta. See
`docs/experiment_log.md` and `docs/error_analysis.md` for slice-level results and
the rejected v3 ablation.

RAG groundedness and citation faithfulness remain planned after the retrieval
scaffold is expanded.

## Limitations

This system is an information organization assistant, not a clinician. The
dataset is tiny and synthetic, and the product default is a deterministic path
rather than the adapter. Outputs must be reviewed before entering canonical memory and by a
qualified medical professional when used for care communication.
