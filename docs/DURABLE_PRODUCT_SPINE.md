# Durable Local Product Spine

The canonical product path is now:

```text
synthetic text/import
  -> immutable source_artifact
  -> explicit ingestion_job (provider/version recorded)
  -> pending record_candidate
  -> family review/edit
  -> atomic approval + record_version + projections + safety/audit events
  -> current timeline head
  -> versioned edit or append-only undo
```

The legacy `src/product_spine.py` remains a replace-on-run evaluation smoke tool.
It is not used as the durable family-memory database.

## Local data location

The default development database is `data/local/coval_health.sqlite`, which is
ignored by Git. Override it without changing code:

```powershell
$env:COVAL_DATA_DIR = "D:\private-coval-health"
# or set one exact file:
$env:COVAL_HEALTH_DB_PATH = "D:\private-coval-health\coval_health.sqlite"
```

Do not put real family health records in the repository, tests, screenshots,
Narval, Hugging Face, cloud services, or logs. The checked-in fixtures remain
synthetic/public-safe only.

## Schema and migrations

`src/health_memory/migrations/` contains monotonic SQL migrations. The runner
stores a SHA-256 checksum in `schema_migrations` and fails if an already-applied
migration changes.

Required tables are present:

- `family_members`
- `source_artifacts`
- `ingestion_jobs`
- `health_records`
- `record_versions`
- `observations`
- `medication_events`
- `symptom_events`
- `appointments`
- `reminders`
- `candidate_safety_events`
- `safety_events`
- `audit_events`

The implementation also has `record_candidates` and `idempotency_keys`.
Source artifacts, version history, audit/safety rows, idempotency results, and
version fact projections are protected by append-only/immutable triggers.
Machine safety findings are written to append-only `candidate_safety_events`
before review. Candidate and canonical edits cannot change the server-owned
safety object.

Each derived fact retains member/record/version/source IDs, extraction version,
timestamp, confidence, validation state, and source-locator JSON. Full user edit
history is retained through candidate revisions and canonical snapshots.

## API contract

Run locally:

```powershell
cd <repo-root>
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn src.serve.coval_health_api:app --host 127.0.0.1 --port 8000
```

Core routes:

| Route | Purpose |
| --- | --- |
| `GET /health` | API, schema, SQLite integrity, mock/OCR/ASR status |
| `GET/POST/PUT/DELETE /family-members` | Local family context (delete is restricted once history exists) |
| `POST /structure` | Non-persisting deterministic mock contract |
| `POST /ingestions` | Save immutable source + job + pending candidate |
| `PATCH /records/{id}/candidate` | Create a user-edited candidate revision |
| `POST /records/{id}/approve` | Atomically create canonical v1 |
| `PATCH /records/{id}` | CAS-protected canonical edit to a new version |
| `POST /records/{id}/undo` | Copy a prior snapshot into a new head version |
| `GET /records/{id}/versions` | Append-only version history |
| `GET /records/{id}/audit` | Append-only workflow audit |
| `GET /timeline?member_id=...` | Approved current heads only |

All health-memory mutation bodies carry an idempotency key; family-member CRUD is
the narrow setup exception. Ingestion also detects the same source
content/member/kind/event-date under a different retry key. A reused key with a
different request digest returns `409 idempotency_key_reused`.

Pending-candidate edits and approvals require the candidate ID/revision the user
actually reviewed; stale clients get `409 stale_candidate`. Approved edits and
undo require the current `base_version_id`; stale clients get
`409 stale_base_version` and cannot overwrite the current head.
Candidate-edit idempotency is bound to the exact candidate it created; replaying
that result after another reviewer advances the head also returns
`409 stale_candidate` instead of returning or approving the newer revision.

## Tests and quality entry point

Install once and run everything:

```powershell
cd <repo-root>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd apps\coval-health-web
npm.cmd ci
npx.cmd playwright install chromium
cd ..\..
powershell -ExecutionPolicy Bypass -File scripts\run_local_quality.ps1
```

Use `-Install` to let the script install dependencies, or `-SkipBrowser` for a
backend/frontend-only pass. GitHub Actions runs backend, frontend build, privacy
artifact checks, and Chromium E2E without downloading a 7B model.

## Portable vault backup and restore

`scripts/manage_vault.py` provides a model-independent durability path:

```powershell
.\.venv\Scripts\python.exe scripts\manage_vault.py backup `
  --database data\local\coval_health.sqlite `
  --output backups\synthetic-demo.coval `
  --acknowledge-synthetic-only-unencrypted
.\.venv\Scripts\python.exe scripts\manage_vault.py verify `
  --archive backups\synthetic-demo.coval
.\.venv\Scripts\python.exe scripts\manage_vault.py restore `
  --archive backups\synthetic-demo.coval `
  --database <clean-synthetic-restore-path>\coval_health.sqlite `
  --acknowledge-synthetic-only-unencrypted
```

The backup uses SQLite's online backup API rather than copying a live WAL file.
Its manifest records schema/FHIR versions and SHA-256 plus byte length for the
database and exports. Verification rejects duplicate or unsafe ZIP paths,
unexpected files, hash/length mismatches, schema mismatch, SQLite corruption,
and foreign-key errors. Restore refuses an existing target and verifies a
temporary database before the atomic move.

Each member export is an HL7 FHIR R4 `document` Bundle whose first resource is
`Composition`; current approved heads map to `Patient`, `DocumentReference`,
`Observation`, `MedicationStatement`, `AllergyIntolerance`, and `Appointment`
resources. Pending candidates are intentionally excluded. This is a conservative,
lossy portability mapping, not interoperable clinical exchange or conformance to
a national implementation guide; an official
FHIR Validator job remains required before claiming standards conformance.

The v1 archive is deliberately marked `encryption: none`; the CLI requires an
explicit synthetic-only acknowledgement. It is prohibited for real family or
patient data even when the surrounding storage is separately encrypted.
Encryption, key lifecycle/rotation, OS keystore integration, retention/deletion,
and recovery-key UX remain P0 security work before real family data is allowed.

## Safety boundary

The mock provider organizes information. It does not diagnose, prescribe, adjust
medication, or say care is unnecessary. Crisis signals take priority over dosage
requests. Obvious negative contexts such as `无胸痛` and historical dosage facts
such as `医生让我每天吃两片，帮我记录` have regression tests.

This does not establish clinical safety. Real OCR/ASR, local 7B inference,
encrypted backups, reminder workers, PDF reports, and broader safety evaluation
remain later gates. Checksum-verified unencrypted backup/restore and FHIR R4
export are implemented, but they do not pass the real-data privacy gate.
