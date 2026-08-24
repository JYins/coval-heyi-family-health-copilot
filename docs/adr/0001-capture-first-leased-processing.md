# ADR 0001: Persist source before inference and lease processing

Status: accepted, schema v5-v7.

## Context

The original synchronous endpoint called the provider before opening the write
transaction. A provider error or process crash could therefore discard the note.
Calling a 7B model inside `BEGIN IMMEDIATE` would instead block every writer and
still roll back the source on process death.

## Decision

Commit an immutable source and capture state first. Claim processing with an
atomic token/expiry update, run inference outside SQLite, then attach output only
if the token remains current. Failures keep the source and become retryable.

## Rejected alternatives

- Provider first: loses input.
- Provider inside transaction: long write lock and rollback-on-crash.
- Always-async worker: cleaner API but adds lifecycle/packaging complexity before
  the v0.3 local product needs it.
- Lifecycle only in legacy `ingestion_jobs`: requires fabricated provider fields
  before provider selection and couples capture evidence to one attempt.

## Consequences and proof

The success response remains backward-compatible. A failure returns `202` with a
durable capture. Lease expiry may repeat compute after a hard crash, but token CAS
and unique constraints prevent a late/rejected result from becoming memory.
`tests/test_capture_recovery.py` covers failure, restart, concurrent claim,
expiry recovery and reject-vs-late-result.
