# Phase 2b aggregate receipts

These files are the synthetic/public-safe, machine-readable aggregate receipts
from the historical Phase 2b product-context audit. They are copied from the
original frozen run without rewriting internal historical paths.

- `FOUR_ARM_COMPARISON.json` contains the four-arm aggregate metrics used by
  the curated evidence summary.
- `EXPERIMENT_MANIFEST.json`, `RESEARCH_CONTRACT.md`, `CLAIM_LEDGER.csv`, and
  `DATA_INVARIANTS.json` record the frozen contract, identities, claim decisions,
  and synthetic-only data boundary.
- `DETERMINISTIC_BASELINE_RESULT.json` records the preregistered deterministic
  counterexample check.

Raw generations and per-row traces remain intentionally uncommitted. These
receipts make the historical aggregate claims inspectable in a clean clone;
they do not make the old run rerunnable and do not establish clinical safety.
The canonical LF hashes are pinned in the parent `evidence_summary.json` and
verified by `tests/test_public_evidence_integrity.py`.
