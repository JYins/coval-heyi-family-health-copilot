# Phase 2 local inference report

Verified on 2026-08-19 using only the frozen synthetic/public eval rows. This
report establishes an engineering integration result, not clinical validity.

> **Quality-evidence correction (2026-08-20):** the 20-row model prompts used
> in this report included semantic eval IDs and gold-like `input_type` values.
> The provider/API/SQLite integration evidence remains valid, but the model
> quality values below are context-contaminated legacy evidence and must not be
> treated as product-distribution acceptance results. The production-equivalent
> rerun and failed prompt candidate are documented in
> `docs/PHASE_2B_SAFETY_INTENT.md`.

## Outcome

The product now exposes explicit `mock`, benchmark-only `transformers_base`,
`transformers_adapter`, and `llama_cpp` provider boundaries. The accepted v2
PEFT artifact runs locally through FastAPI, SQLite, and Next.js. Model loading is
local-files-only, Hugging Face offline flags are set, and a process socket guard
rejects non-loopback connections. No provider silently falls back to mock.

The engineering integration passed. The frozen same-local quantization quality
gate is **not evaluable**, because this 8 GB-class GPU cannot run the required
same-machine unquantized accepted-provider comparator. Historical Narval scores
are shown only as descriptive context, not substituted for that comparator.
Deployment remains **blocked** because the local path has large descriptive
historical gaps on two slices and serious false-refusal regressions. `mock`
therefore remains the default product runtime.

## Frozen artifacts and runtime

- Base: `Qwen/Qwen2.5-7B-Instruct`, exact revision
  `a09a35458c702b33eeacc393d103063234e8bc28`.
- Base download: 11 files and 15,242,788,168 bytes. Manifest sizes and all four
  weight-shard SHA-256 values were verified.
- Adapter weights: 80,792,096 bytes, SHA-256
  `b874d8dbc9885c51577a06ad9738f0a418210fc9acb3f633effae192c3aa54e0`.
- Hardware: NVIDIA GeForce RTX 5060 Laptop GPU, 8,151 MiB reported VRAM.
- Measured runtime: Python 3.12.12, PyTorch
  `2.12.0.dev20260226+cu128`, CUDA 12.8, Transformers 4.57.6, PEFT 0.20.0,
  bitsandbytes 0.50.1.
- Quantization: bitsandbytes NF4 4-bit, double quantization, float16 compute.

The measured wrapper inherited an existing local runtime. The separate
`scripts/setup_local_model_runtime.ps1` installer defines a bounded compatibility
environment (with an exact Torch pin and version ranges elsewhere); it is not a
full lock file and is not represented as the measured environment.

## Offline simulation

Physical disconnection was intentionally not performed. Benchmark, adapter
effect, API, browser E2E, and process-restart checks set `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`, use explicit local paths with
`local_files_only=True`, reject remote model code, and install a process-level
socket guard that allows loopback only. The browser still talks to the local API
over loopback. This is simulated-offline evidence, not a true air-gap claim.

## Fixed synthetic quality comparison

All current providers used the same 20 frozen rows, exact schema_v3 prompt,
greedy decoding, normalization, deterministic summary renderer, safety overlay,
and evaluation scripts. The safety values below describe the combined model and
deterministic safety layer, not raw model behavior.

| Slice | n | Mock F1 | Base NF4 F1 | v2 NF4 F1 | v2 - base | Historical accepted v2 | v2 - historical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `synthetic_v0` | 10 | 0.2826 | 0.6970 | 0.6870 | -0.0100 | 0.7656 | -0.0786 |
| `medication_contrast_v0` | 4 | 0.0800 | 0.8966 | 0.8966 | +0.0000 | 0.9032 | -0.0066 |
| `safety_onset_edge_v1_1` | 6 | 0.0571 | 0.7500 | 0.7500 | +0.0000 | 0.8261 | -0.0761 |

The local v2 path retained refusal recall 1.0, crisis recall 1.0 where
applicable, false escalation 0, hallucination 0, and overdiagnosis 0. Its false
refusal rates were 0.1429, 1.0000, and 0.2500 across the three slices; the
medication slice therefore falsely refused both benign examples. This safety
regression independently blocks deployment.

The adapter was active. An enable/disable forward probe measured maximum
absolute logit delta 0.6396484375, mean absolute delta 0.1628172696, and L2
delta 72.6388092041. The first-token argmax remained token 515 in both cases;
the probe establishes LoRA participation, not output-quality improvement.

## Latency

| Run | Cold load | Warm p50 | Warm p95 | Warm mean | Peak CUDA allocated | Benchmark wall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mock rules | 0.000 ms | 0.095 ms | 0.709 ms | 0.173 ms | n/a | not comparable |
| Base NF4 | 31.226 s | 12.333 s | 15.980 s | 12.215 s | 5,850,974,720 B | 275.976 s |
| v2 adapter NF4 | 30.753 s | 19.933 s | 30.630 s | 20.547 s | 5,931,715,072 B | 442.179 s |

TTFT and tokens/second were not instrumented and are not estimated. Historical
latency was not recorded. The adapter run was slower under this setup, but the
run order and generated token counts were not controlled tightly enough to
attribute the whole difference causally to PEFT overhead.

## Synthetic product E2E and restart

With `COVAL_MODEL_PROVIDER=transformers_adapter` and the API process socket
guard enabled, Playwright passed 2/2 tests in approximately 1.0 minute. The
tested flow was local v2 generation -> browser review -> SQLite save ->
append-only v1/v2/v3 -> undo -> refresh -> persisted extraction-version and
source-evidence reload. The
second test verified visible write disablement on API failure.

An opt-in real-provider process test also passed in 45.665 seconds: it started
Uvicorn with the adapter and socket guard, ingested and approved a synthetic
record, terminated the process, started a second process on the same SQLite
file, and verified the provider/model/prompt/contract provenance after reload.
The opt-in run also wrote a machine-readable PASS record to
`results/phase2_local_inference/real_provider_restart_audit.json`.

Both base and adapter benchmarks produced 20/20 contract-valid predictions in
one generation attempt per row. No second generation repair was used; narrow
deterministic schema normalization remains tested for legacy-shaped output.

## Decision and evidence boundary

- Provider/API/browser/SQLite integration: **pass**.
- Simulated-offline execution with a non-loopback socket guard: **pass**.
- JSON/product contract: **pass**, 20/20 in one attempt for base and adapter.
- Same-local unquantized-vs-NF4 quality gate: **not evaluable**.
- Deployment: **blocked** by the false-refusal regression and descriptive
  historical gaps.
- GGUF/llama.cpp: interface only; no GGUF artifact or benchmark was run.
- Research claim promotion: **not passed**. Review was internal-only/degraded;
  no external blind peer plus human claim sign-off was performed.

Ignored machine outputs live under `results/phase2_local_inference/`. The base
and adapter benchmark summaries bind the exact source-file hashes, including
the shared provider source SHA-256
`581ed677f9dc280f6076dacc95a4c06c1470cbc9021bd6a02eb752fb489d2204`.

Reproduction entry points:

```powershell
.\.venv-model-gpu\Scripts\python.exe scripts\benchmark_local_provider.py
.\.venv-model-gpu\Scripts\python.exe scripts\verify_adapter_effect.py
.\.venv\Scripts\python.exe scripts\compare_local_inference.py
```
