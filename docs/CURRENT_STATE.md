# Coval Health Current-State Matrix

Last verified: 2026-08-28

This matrix separates shipped product behavior, controlled mocks, measured research,
and planned work. Passing a synthetic test does not establish clinical validity.

| Area | State | Evidence / boundary |
| --- | --- | --- |
| SQLite health memory | Implemented and tested | Numbered, checksum-verified migrations; FK/integrity checks; immutable source artifacts; source-aware content deduplication; candidate revisions; append-only record versions and fact projections. |
| Capture-first recovery | Implemented and tested | Source text commits before inference. Expiring token leases serialize retries; provider failure is durable/retryable, and reject invalidates late output. |
| Candidate review and approval | Implemented and tested | API and browser flow: ingest -> edit candidate -> approve v1. Candidate ID/revision CAS prevents stale review, and server-owned safety cannot be downgraded by an edit. Unapproved candidates do not enter the canonical timeline. |
| Record edit and undo | Implemented and tested | CAS (`base_version_id`) rejects stale writes. Undo copies an old snapshot into a new head version instead of changing history. |
| Idempotent ingestion | Implemented and tested | Database-backed key + request digest. Same key/same payload reuses the result; same key/different payload returns 409. Concurrent duplicate test uses ten writers. |
| Restart persistence | Implemented and tested | Automated test terminates the Uvicorn process, starts a new process over the same on-disk database, and reloads the approved record. |
| Next.js product flow | Implemented and browser-tested | API-backed member list/creation, arbitrary editable note/source/date, recovery inbox, editable review, server-confirmed save, v2 edit, v3 undo, refresh recovery. Mock and real local-v2 Playwright paths were exercised. |
| Deterministic structuring provider | Mock, explicitly labeled | `mock-rules-v2`; includes conservative crisis/dosage rules and obvious-negation handling. It is not the trained LoRA runtime. |
| Qwen2.5-7B LoRA local runtime | Connected historically, measured, deployment-blocked | Local NF4 v2 ran through API/browser/SQLite with simulated-offline guards. The frozen same-local unquantized comparator does not fit this GPU, so that gate is not evaluable; false refusals and descriptive historical gaps block deployment. Runtime paths are now labeled identity-unverified until a pinned file-hash manifest is implemented. Mock remains the default. See `docs/PHASE_2_LOCAL_INFERENCE.md`. |
| OCR / ASR | Stub | UI accepts synthetic/pasted text modes, but no real OCR or ASR engine runs. |
| Reminders / weekly report | Schema or UI plan only | `reminders` table exists; no scheduler, notification worker, daily check-in, or weekly report worker is implemented. |
| Portable backup / restore / FHIR R4 export | Implemented with explicit privacy block | Consistent SQLite snapshot, SHA-256/size accidental-corruption checks, clean-path restore drill, migration ledger/checksum validation, and per-member FHIR R4 document Bundles are tested. Archive format v1 is unsigned and unencrypted; no SQLCipher, OS keystore, encrypted backup, key rotation, official FHIR Validator run, or doctor PDF yet. |
| RAG | Measured retrieval scaffold only | Tiny 7-document / 8-query synthetic/public-safe smoke set; not a production retrieval or generation system. |
| GGUF / llama.cpp local inference | Interface only | An explicit local-file-only provider exists, but no verified merge, GGUF export, quantization artifact, or llama.cpp benchmark has run. |
| Multi-user auth / clinical deployment | Out of current scope | Local single-user prototype; no claim of clinical effectiveness, regulatory compliance, or hostile-local-machine protection. |
| Real-data mode | Executable fail-closed gate | `COVAL_REAL_DATA_MODE=1` raises until encryption, key recovery, auth, encrypted backup, purge and fixed packaged SQLite gates pass. Current stdlib SQLite 3.50.4 lacks the documented 2026 WAL-reset fix. |

## Verified commands

```powershell
cd <repo-root>
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

cd apps\coval-health-web
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e
npm.cmd audit --audit-level=high
```

The 2026-08-28 final audit reran the full command above after evidence and source-
provenance hardening: 57 backend/API/process/provider/vault/security tests ran,
56 passed, and the opt-in real-provider restart audit was skipped; frontend lint,
typecheck and production build passed; Playwright passed 2/2.
The earlier opt-in real local-v2 browser evidence remains historical evidence in
`docs/PHASE_2_LOCAL_INFERENCE.md`; it was not rerun without a pinned identity manifest.
Its Phase 2b aggregate comparison and research contract are now committed under
`artifacts/public/phase2b_safety_intent/receipts/` with canonical hash checks;
raw generations and per-row traces remain intentionally uncommitted.
