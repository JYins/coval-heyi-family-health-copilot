---
license: other
base_model: Qwen/Qwen2.5-7B-Instruct
library_name: peft
pipeline_tag: text-generation
language:
  - zh
tags:
  - lora
  - qlora
  - medical-structuring
  - chinese
  - family-health
  - synthetic-data
private: true
---

# Coval HeYi Qwen2.5 7B LoRA Adapter

This is a LoRA adapter for a private-first Chinese family health memory copilot prototype.

The project focuses on evaluation-first Chinese medical record structuring, visit-prep summaries, and safety boundary handling for family users. It is not a diagnostic, prescription, or medication-adjustment system.

## Base Model

- Base model: `Qwen/Qwen2.5-7B-Instruct`
- Adapter: LoRA SFT v2
- Product layer: deterministic summary template patch

## Data Boundary

This adapter and its evaluation artifacts use synthetic/public examples only.

Real family medical data, private patient data, scans, local databases, and personally identifying records are not used for training, evaluation, logs, or upload.

## Intended Use

Intended:

- Structure Chinese family health notes, report snippets, medication notes, symptom logs, and appointment-related text.
- Prepare doctor-facing communication summaries.
- Flag medication-advice requests and crisis symptoms for safer handling.
- Support a local/private family health memory app.

Not intended:

- Diagnosis.
- Treatment recommendation.
- Prescription or medication dose adjustment.
- Replacing clinician review.
- Emergency triage as a standalone medical device.

## Current Evaluation Summary

Current product/demo default:

`Qwen/Qwen2.5-7B-Instruct + LoRA SFT v2 + deterministic summary patch`

Selected recovered/template metrics:

| Eval slice | Extraction F1 | Summary strict | Summary relaxed | Safety refusal | Crisis recall | Hallucination / overdiagnosis |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthetic_v0 | 0.7656 | 0.3784 | 0.8108 | 1.0000 | 1.0000 | 0.0000 / 0.0000 |
| medication_contrast_v0 | 0.9032 | 0.5556 | 0.9444 | 1.0000 | not applicable | 0.0000 / 0.0000 |
| safety_onset_edge_v1_1 | 0.8261 | 0.2105 | 0.9474 | 1.0000 | 1.0000 | 0.0000 / 0.0000 |

SFT v3 was also trained and evaluated as a targeted failure-driven ablation. It completed successfully, but it was not adopted because it did not improve the current v2 + deterministic patch candidate and regressed on `synthetic_v0` strict summary and false refusal.

## Safety Notes

The surrounding application should enforce:

- no diagnosis or prescription claims;
- no medication dose adjustment advice;
- crisis escalation language for dangerous symptoms;
- user review before saving OCR/ASR extracted facts;
- provenance for every structured field.

## Deployment Notes

The intended product deployment is local-first:

- Next.js web app;
- FastAPI API;
- SQLite local family memory store;
- optional worker for OCR/ASR jobs and weekly reports;
- selectable model backend: local adapter, local smaller model, or configured API provider.

## Limitations

- Evaluation set is small and synthetic/public.
- The adapter should not be used with real patient data without a separate privacy, safety, and clinical validation process.
- The deterministic product-layer summary patch is part of the current best system and should be documented alongside the adapter.
