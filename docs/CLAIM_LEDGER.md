# Public claim ledger

Use this file to keep README, resume and interview wording tied to executable
evidence. The baseline release implementation commit `4f94357` was reproduced
from a clean local clone and merged into `main` at `2a4dd33`; GitHub Actions run
`32696464754` exercised that main merge. The 2026-08-28 hardening audit is recorded
in `docs/experiment_log.md`; none of these receipts imply clinical validation.

| Claim | Status | Evidence | Boundary |
| --- | --- | --- | --- |
| immutable source evidence | release-commit verified | migrations, store constraints/tests | local synthetic/public data |
| identical content from distinct sources remains distinct | locally verified 2026-08-28 | migration v8 + provenance regression test | source-label identity; not a full content-blob/event split |
| capture survives provider failure | release-commit verified | `test_capture_recovery.py` | synchronous local API; lease expiry may repeat compute |
| review before timeline | release-commit verified | API/store/Playwright | user confirmation, not clinician validation |
| append-only versions and undo | release-commit verified | schema/API/restart/E2E | undo creates a new version |
| deterministic safety floor | release-commit verified | provider/safety tests | conservative rules, not clinical effectiveness |
| candidate rejected by eval gate | historical decision record | Phase 2/2b reports and experiment log | synthetic targeted slices |
| local v2 adapter connected | historical local evidence; optional | Phase 2 reports and curated evidence summary | NF4 path; not clean-clone reproducible or product default |
| clean-clone model evidence is stable | locally verified 2026-08-28 | committed evidence summaries + integrity/contract tests | historical synthetic audit; candidate blocked |
| backup/restore tested | release-commit verified v1 | vault tests | unencrypted and unsigned |
| FHIR R4 export | release-commit-verified conservative mapping | FHIR round-trip tests | not official-validator conformance |
| real-family-data ready | **blocked** | executable security gate | requires all threat-model gates |
| production RAG / OCR / ASR | not implemented | current-state matrix | interfaces/stubs only |

## Resume wording after clean-clone CI passes

> Built a synthetic-only local family-health memory platform with immutable
> source provenance, capture-first failure recovery, review-before-save,
> append-only versions, tested backup/restore, deterministic safety controls,
> conservative FHIR R4 mapping, and model-evaluation gates that rejected unsafe
> candidates.

> Integrated a local Qwen2.5-7B LoRA NF4 provider, then kept the deterministic
> path as default when frozen safety/comparator gates did not justify promotion.

Do not shorten “synthetic-only”, “conservative mapping”, or “unencrypted v1” out
of public claims until their corresponding gates change state.

Baseline main receipt: [GitHub Actions run 32696464754](https://github.com/JYins/coval-heyi-family-health-copilot/actions/runs/32696464754)
passed backend policy/tests, frontend lint/typecheck/build, and Chromium E2E.
