# Model Card Draft: med-structurer-zh

Status: draft; no model has been trained yet.

## Intended Use

Structure Chinese health reports, symptom notes, and medication/reminder information into a longitudinal health record, then generate clinician-facing summaries and family update drafts.

## Out Of Scope

- Diagnosis.
- Medication dosage advice or adjustment.
- Reassurance that medical care is unnecessary.
- Emergency triage beyond conservative escalation guidance.

## Training Data

To be filled after data selection. Only public or synthetic data is allowed for train/eval artifacts that may be published.

## Evaluation

Planned metrics:

- Field-level extraction F1.
- Summary coverage and unsupported-claim rate.
- Safety refusal rate.
- Crisis escalation recall.
- Hallucination and overdiagnosis rates.
- RAG groundedness and citation faithfulness after the RAG phase.

## Limitations

This system is an information organization assistant, not a clinician. Outputs must be reviewed by a qualified medical professional.
