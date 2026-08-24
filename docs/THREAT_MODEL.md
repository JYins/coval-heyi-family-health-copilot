# Threat model and real-data gate

Status: synthetic/public-safe release only. `COVAL_REAL_DATA_MODE=1` fails
closed. This document is an engineering boundary, not a compliance claim.

## Assets

- raw notes, report text, source hashes and member identity;
- canonical timeline, candidate/version/audit/safety history;
- model prompts/outputs and evaluation artifacts;
- SQLite database, WAL/SHM files, exports, backups and future keys.

## Threats addressed in the current release

| Threat | Current control |
| --- | --- |
| model/provider failure loses input | source is committed before inference; failed capture is listed and retryable |
| duplicate browser submit | key + request digest and transaction-level uniqueness |
| two retries run concurrently | atomic lease/CAS; only the lease owner may attach output |
| late output revives rejected work | reject invalidates lease; stale token fails |
| model silently becomes trusted memory | review-before-save and canonical timeline query only |
| stale browser overwrites review | candidate/version CAS |
| model weakens safety result | deterministic OR overlay and server-owned safety fields |
| archive corruption/path abuse | hashes, byte/count/ratio limits, path validation, same-handle verification, clean restore |
| provider silently downloads/falls back | local-path validation and no mock fallback; the fixed benchmark/test wrapper also sets offline flags and blocks non-loopback sockets |
| obvious private fixtures enter public tests | synthetic/public-only policy plus CI path/name checks; these checks reduce risk but cannot prove that arbitrary text is de-identified |

## Threats not yet addressed

- database/WAL/SHM and vault v1 are not encrypted at rest;
- no authenticated same-origin session or hostile-local-process defense;
- no independent recovery key or encrypted backup v2 restore drill;
- no verified purge across live data, exports, caches and backups;
- no signed Windows installer/SBOM or clean-VM offline release proof;
- no official FHIR Validator run and no clinical/regulatory validation.

The current machine reports an SQLite runtime in the affected range of the
2026 WAL-reset bug. SQLite documents the fix in 3.51.3 and backports 3.50.7
and 3.44.6. A packaged real-data runtime must pin a fixed build and pass a
multi-connection checkpoint stress test. See the
[SQLite WAL documentation](https://www.sqlite.org/wal.html#the_wal_reset_bug).

## Gate required before a first real record

All items are mandatory:

1. SQLCipher (or an equivalently reviewed full-database design) encrypts DB,
   WAL, SHM, temp and indexes; wrong/missing keys fail without creating a new DB.
2. A random key is protected by Windows current-user DPAPI, never an environment
   variable; an independent offline recovery secret succeeds on a clean profile.
3. All business routes require an HttpOnly, SameSite=Strict local session;
   Origin/Host/CSRF and cross-member IDOR tests fail closed; actor is server-owned.
4. Backup v2 uses a mature authenticated encrypted container and proves wrong-key,
   tamper, truncation and new-machine restore behavior.
5. Purge/full-reset semantics are tested across DB, WAL, exports, logs, caches and
   app-managed backups, with explicit limits for external copies.
6. Production logs pass PHI/token canary scans and do not persist prompt/output.
7. A signed, pinned, fixed-SQLite Windows package installs and runs offline on a
   clean standard-user VM; SBOM and third-party notices are published.

## Explicit non-goals

This design does not protect an unlocked Windows account from administrator/
kernel malware, screen capture, keylogging or process-memory inspection. It does
not establish PIPL/PIPEDA/HIPAA, medical-device, FHIR-conformance or clinical-
effectiveness compliance.
