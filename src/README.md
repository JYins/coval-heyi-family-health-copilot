# Source Layout

- `ocr/`, `asr/`: input processing adapters.
- `structure/`: model prompts/parsers for structured health records.
- `timeline/`: SQLite/Postgres schemas and timeline queries.
- `summary/`: doctor-facing summary and family weekly report generation.
- `safety/`: crisis symptom rules and medical-safety refusals.
- `serve/`: local inference/UI service.

Use skeleton-first, fail-loud implementation style.

## Current Local Spine

`product_spine.py` is the first fake-data end-to-end spine:

```powershell
python src\product_spine.py --gold eval\gold\synthetic_v0.jsonl --pred eval\gold\fixture_predictions_v0.jsonl --database results\product_spine\synthetic_v0.sqlite --out results\product_spine\synthetic_v0_report.json --markdown-out results\product_spine\synthetic_v0_doctor_summary.md
```

It uses synthetic fixture predictions only. It creates a SQLite timeline with reports,
lab items, medications, symptoms, appointments, and safety events, then writes a
machine-readable organization report and an optional doctor-facing Markdown summary.
It is not a model result and not medical advice.
