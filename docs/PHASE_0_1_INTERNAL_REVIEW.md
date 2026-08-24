# Phase 0/1 Internal Review Record

Date: 2026-08-19

Review status: `INTERNAL_REVIEW_ONLY / DEGRADED_REVIEW`

The user explicitly chose Codex subagents instead of Kimi or Claude. This record
therefore documents independent internal reviews; it is not external peer
verification and must not be described that way.

## Scope

The review covers only the prompt's Phase 0 truth/reproducibility repair and
Phase 1 durable product spine. It does not approve clinical use, real family
data, local 7B inference, OCR/ASR, reminders, reports, encryption, backup/restore,
RAG generation, or deployment.

## Independent review sequence

1. A blind architecture reviewer recommended native SQLite with numbered
   migrations, immutable sources, review-before-save, append-only versions,
   database idempotency, candidate/version CAS, and process-level restart tests.
2. An adversarial reviewer defined failure tests for provenance, duplicate
   submission, stale writes, undo, API outages, safety negation, and privacy.
3. A fresh final reviewer inspected the implemented diff and found four high
   issues plus repository/test hardening items. The implementation was revised
   and re-tested before closure. Two focused remediation passes then found and
   fixed term-local negation and candidate-idempotency replay edge cases. The
   final focused pass reported no remaining blocking, high, or medium issue in
   the Phase 0/1 remediation scope.

## Findings and dispositions

| Finding | Disposition |
| --- | --- |
| Crisis variants and comma-scoped negation could miss escalation | Added variants and punctuation-aware scope; regression cases now include `肢体无力`, `呼吸越来越困难`, `没有发热，胸痛`, explicit negatives, dosage contrast, and crisis priority. |
| Client-authored candidate safety could be downgraded | Safety is server-controlled for candidate and canonical edits. Migration 0003 adds append-only candidate safety evidence before approval, including backfill. |
| Candidate edit/approval could act on an unseen newer revision | Both operations now require the reviewed candidate ID and revision and return `409 stale_candidate` on mismatch. |
| Broad `无` matching suppressed affirmed crisis phrases such as `无缓解的胸痛` | Replaced clause-wide substring matching with term-local and explicit coordinated-negation patterns; added both reviewer examples as regression tests. |
| A replayed candidate-edit key could return a later candidate | Idempotency now stores the exact created candidate ID, rejects replay when it is no longer current, and includes the base candidate identity in the frontend key. Migration 0004 invalidates ambiguous legacy development keys. |
| Concurrent initialization could lock or race migrations | Connections close on setup failure; WAL initialization is bounded; migration existence is rechecked under `BEGIN IMMEDIATE`; a ten-writer initialization test passes. |
| Generated results, temporary files, and Next build trees polluted privacy scans/status | Added an explicit results allowlist, ignored `tmp/` and generated logs, skipped `.next-*` in the scanner, and expanded the tracked-artifact CI gate. |
| Duplicate Python test name hid one test | Split it into uniquely named CRUD and history-delete-guard tests and added the missing safety/CAS/startup cases. |
| Documentation claimed every write had an idempotency key | Narrowed the claim to health-memory mutations and explicitly documented family-member CRUD as the setup exception. |

## Verification evidence

The following commands passed on 2026-08-19:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_local_quality.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1
cd apps\coval-health-web
npm.cmd audit --audit-level=high
```

Observed results:

- workflow/privacy policy check: pass;
- backend/API/database/process tests: 10 passed;
- real Uvicorn stop/restart over the same SQLite file: passed;
- frontend lint, typecheck, and Next.js production build: passed;
- Playwright: 2 passed, covering durable v1/v2/undo-v3/reload/duplicate behavior
  and visible API failure with writes disabled;
- dependency audit: 0 known vulnerabilities;
- local generated `results/` and `tmp/` files visible to normal Git add: 0.

## Decision boundary

The narrow Phase 0/1 gate is an internal pass for synthetic data: an approved
record survives a real backend restart, preserves source hash/extraction version
and append-only history, and does not silently save while the API is offline.

This does not establish clinical safety, production durability, privacy against
a hostile local machine, encrypted storage, or readiness for real family data.
