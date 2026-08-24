# Architecture: evidence before intelligence

Coval HeYi has two independent planes: a usable synthetic/public-safe local
product and a model-evaluation program. The model is replaceable; source
evidence, review, versions, and deterministic safety are not.

```text
editable note / OCR text / transcript
                |
                v
       immutable source_artifact  <--- persisted before inference
                |
          atomic lease/CAS
                |
                v
   explicit provider interface --------> mock | base | historical v2 (deployment-blocked) | llama.cpp
                |                         (no silent fallback)
                v
     machine candidate + safety event
                |
          family review/edit
                |
                v
 append-only canonical version -------> timeline / doctor brief / FHIR mapping
                |
                v
       verified snapshot/restore
```

## Components and trust boundaries

| Component | Responsibility | Does not own |
| --- | --- | --- |
| Next.js workbench | editable intake, member selection, recovery inbox, review and approval | medical truth, authorization, model safety |
| FastAPI contract | validation, workflow transitions, provider invocation, stable error codes | cloud sync or diagnosis |
| SQLite store | immutable source, idempotency, leases, CAS, append-only versions, audit/safety evidence | at-rest confidentiality in the current release |
| Provider boundary | explicit local model/runtime selection and provenance | canonical save authority |
| Deterministic safety overlay | dosage-request refusal and crisis escalation floor | clinical diagnosis or reassurance |
| Vault v1 | online snapshot, resource limits, hashes, clean restore drill, conservative FHIR mapping | encryption, sender authenticity, FHIR conformance |

## Capture lifecycle

```text
captured -> processing -> needs_review -> completed
    |           |              |
    |           v              v
    +----> failed_retryable   rejected
                 |
                 +----> processing
```

`processing` is protected by a token and expiry. The provider runs outside a
database transaction. A late result may attach a candidate only while its token
still owns the lease; rejection invalidates the lease. A crashed worker becomes
retryable after lease expiry. The database constraints remain the final defense
against duplicate records.

The capture lifecycle is source-aligned rather than embedded in the older
`ingestion_jobs` row. That was deliberate: a source can exist before a provider
is available or selected, while the legacy job schema requires provider/model
provenance. The additive table avoids fabricating provenance and migrates old
v4 databases without rewriting immutable source or record history.

## Invariants worth discussing in an interview

1. A provider error cannot erase submitted source text.
2. Unapproved candidates never appear in the canonical timeline.
3. Source payloads are immutable; corrections create candidate/version history.
4. Idempotency is bound to both a key and request SHA-256; key reuse with changed
   content fails with `409`.
5. Review and record edits use compare-and-swap identifiers to reject stale UI.
6. Safety evidence is server-controlled and append-only; a user edit cannot
   downgrade the original model/deterministic safety result.
7. Provider selection is explicit and missing local weights fail closed.
8. Real-data mode is executable code, not a README promise: requesting it raises
   until encryption, authentication, recovery, deletion, and packaging gates pass.

## Verification map

| Risk | Executable evidence |
| --- | --- |
| lost input after model failure | `tests/test_capture_recovery.py` |
| duplicate/concurrent processing | lease winner and ten-writer tests |
| stale or forged review | candidate/version CAS tests |
| unsafe candidate promotion | provider safety tests and frozen research gates |
| restart data loss | `tests/test_process_restart.py` |
| corrupt or malicious archive | `tests/test_vault_backup.py` |
| browser-only fake success | Playwright durable-memory E2E |

See the ADRs under `docs/adr/` for rejected alternatives and trade-offs.
