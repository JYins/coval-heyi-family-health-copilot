# Evaluation Harness

Build this before training.

Planned metric modules:

- `metrics_extract.py`: field-level structured extraction F1.
- `metrics_summary.py`: strict coverage, relaxed diagnostic coverage, and unsupported-claim checks.
- `metrics_safety.py`: refusal and medical-safety boundaries.
- `metrics_crisis.py`: crisis symptom escalation recall.
- `metrics_risk.py`: first-pass hallucination and overdiagnosis rates from forbidden claims.
- `run_eval.py`: one entry point that writes machine-readable metrics and optional per-example details.

Gold examples belong in `eval/gold/` and must be public/synthetic.

## Current Smoke Test

The first synthetic fixture can be run with:

```powershell
python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred eval\gold\fixture_predictions_v0.jsonl --out results\eval_fixture_metrics.json
```

This is not a model result. It only proves the metric harness and JSONL contract work.

For baseline failure analysis, also write a per-example report:

```powershell
python eval\run_eval.py --gold eval\gold\synthetic_v0.jsonl --pred eval\gold\fixture_predictions_v0.jsonl --out results\eval_fixture_metrics.json --details-out results\eval_fixture_details.json
```

Medication safety contrast cases are kept separate from `synthetic_v0` so earlier baseline runs remain reproducible:

```powershell
python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred eval\gold\fixture_predictions_medication_contrast_v0.jsonl --out results\eval_medication_contrast_metrics.json --details-out results\eval_medication_contrast_details.json
```

When a model already produces product-ingestible `structured` and `safety` fields, test whether the doctor-facing summary problem can be solved by the product layer before training another model:

```powershell
python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_template_summary.jsonl
python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_template_summary.jsonl --out results\medication_contrast_schema_v3\metrics_template_summary.json --details-out results\medication_contrast_schema_v3\example_details_template_summary.json
```

This template is a product-spine comparison, not a model-quality claim. It does not read gold summary points.

To test the current best medication-contrast product path, add deterministic report-type normalization before the template summary:

```powershell
python scripts\normalize_report_types.py --pred results\medication_contrast_schema_v3\predictions_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_report_type_normalized.jsonl --report results\medication_contrast_schema_v3\report_type_normalization_report.json
python scripts\template_doctor_summary.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_report_type_normalized.jsonl --out results\medication_contrast_schema_v3\predictions_report_type_template_summary.jsonl
python eval\run_eval.py --gold eval\gold\medication_contrast_v0.jsonl --pred results\medication_contrast_schema_v3\predictions_report_type_template_summary.jsonl --out results\medication_contrast_schema_v3\metrics_report_type_template_summary.json --details-out results\medication_contrast_schema_v3\example_details_report_type_template_summary.json
python scripts\compare_medication_contrast.py
```

This postprocess may normalize labels, but it must not change `safety.refused` or `safety.escalated`.
