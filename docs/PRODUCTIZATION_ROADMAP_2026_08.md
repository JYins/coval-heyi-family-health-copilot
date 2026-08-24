# Coval Health Productization Roadmap

Last reviewed: 2026-08-23

## Product thesis

Coval Health should be a durable, local family-health memory system with an
evaluation-gated model, not a medical chatbot whose prose becomes the database.
The system of record is confirmed structured data plus immutable source evidence;
the model is a replaceable extraction and drafting component.

The strongest portfolio claim is therefore:

> Built a local family-health memory system with evidence-linked extraction,
> review-before-save, append-only versions, tested recovery, deterministic safety
> controls, and model promotion gates that reject unsafe candidates.

Do not yet claim production security, clinical validation, implemented OCR/ASR,
or a deployed medical copilot.

## What is real today

- FastAPI/SQLite/Next.js synthetic workflow: source -> candidate -> family review
  -> approval -> versioned timeline -> edit/undo.
- Migration checksums, foreign keys, immutable sources, append-only history,
  idempotent ingest, stale-write rejection, audit/safety events, and real process
  restart persistence.
- Explicit mock/base/adapter/llama.cpp provider boundary. Local v2 NF4 adapter
  inference has run through API/browser/SQLite, but remains deployment-blocked.
- A leakage-controlled four-arm Phase 2b evaluation rejected a prompt candidate
  after it missed crisis and unsafe-request cases. The deterministic mock path
  remains the product default.
- Portable vault v1: consistent SQLite snapshot, per-file SHA-256/size manifest,
  clean-path restore, migration-history checks, and conservative per-member FHIR
  R4 document export. The archive is unencrypted and unsigned.

## Current real-use blocker

The current browser is still a polished synthetic demo: members and samples are
front-end constants and the intake textarea is read-only. More importantly,
`POST /ingestions` calls the provider before persisting the source. A provider
timeout, OOM, 503, or invalid model response can therefore discard new input.

The next implementation slice must be a **capture-first manual memory inbox**:

1. Load/create/edit family members from the API; store date of birth and timezone
   instead of treating age as durable identity data.
2. Make text, event date, and source editable; keep synthetic presets as an
   explicit demo mode.
3. Persist immutable source evidence before calling any model.
4. Add ingestion states (`captured`, `processing`, `needs_review`, `failed`,
   `rejected`, `approved`), pending/failed lists, idempotent retry, and reject.
5. If the provider fails, retain the note and allow manual structuring.
6. Prove refresh, API restart, provider failure, retry, review, approval, edit,
   undo, and timeline recovery in browser E2E.

Acceptance gate: a user can create a synthetic member and arbitrary synthetic
note from a clean start, lose the provider and restart the app without losing the
capture, then finish review and recover the approved record.

## P0 before any real family data

### Security and data rights

- Local authentication and server-owned actor identity; do not trust an actor or
  member scope supplied only by the browser.
- Per-member roles/consent: owner, caregiver, read-only, and emergency-summary.
- Encryption for database, attachments, indexes, caches, and backups using a
  reviewed library; keep master keys in the OS keystore and design recovery/key
  rotation separately.
- No advertising SDK or health-content analytics. Logs must omit names, source
  text, model prompts, and report contents.
- Explicit export, retention, consent withdrawal, member purge, and full-vault
  reset. Normal edits remain append-only; destructive purge requires confirmed
  reauthentication and a documented backup-retention policy.
- Encrypted backup plus restore drill, RPO/RTO, old-schema migration fixtures,
  corruption and interrupted-upgrade tests.

NIST treats storage encryption as a threat-dependent system choice rather than a
single checkbox, and its key-management guidance covers the full key lifecycle.
See [NIST SP 800-111](https://csrc.nist.gov/pubs/sp/800/111/final) and
[NIST key-management guidance](https://csrc.nist.gov/Projects/Key-Management/Key-Management-Guidelines).

China's PIPL identifies medical-health data as sensitive personal information
and sets additional requirements around necessity, protection and consent. The
exact duties depend on who operates the product and its data flows; see the
[official NPC text](https://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html).

### Stable model output

- Keep strict JSON schema, bounded retry, prompt/model/schema/generation version
  pinning, and deterministic crisis/unsafe-medication overlay.
- Persist field-level source page/span, uncertainty, model confidence, and human
  review state separately. User confirmation must not turn model confidence into
  a fabricated `1.0`.
- Generate doctor summaries deterministically from current confirmed facts;
  every important item links back to source evidence.
- Use a frozen, blind, product-equivalent corpus. Gate contract validity,
  extraction F1, temporal/negation/subject accuracy, unsupported-fact rate,
  crisis sensitivity, unsafe-action refusal, benign false refusal, latency,
  memory, cold start, and long-document degradation.
- Select base, adapter, or another local model by the gate. LoRA does not have to
  win. Provider failure falls back to manual review, never to invented facts.

NIST's GenAI profile treats confabulation as a core generative-model risk and the
AI RMF calls for repeatable testing and documented risk management:
[NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) and
[NIST GenAI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf).

## P1: make the memory longitudinally useful

- Current-fact SQL views that join only `health_records.current_version_id`, so
  edits and undo do not double-count projections.
- Cursor-paginated search/filter by member, date, type, symptom, medicine and
  observation.
- Normalized numeric observations, units, reference ranges, abnormal flags and
  terminology aliases while retaining raw text.
- Medication reconciliation across start/stop/missed/reported events, explicit
  conflicts, and “unknown current status” rather than guessed active medication.
- Questions such as: latest value and source, six-month trend, repeated symptom,
  medication start/stop history, unresolved conflict, and missing follow-up.
- A 6-12 month multi-member synthetic benchmark with exact answer, provenance,
  temporal consistency, conflict handling and p95 query latency.

This benchmark is likely the project's most distinctive research contribution:
it tests long-term health memory rather than another generic chat score.

## P1: real local ingestion

Implement one vertical slice at a time:

1. PDF/image -> local OCR -> page/bounding-box locator -> review -> confirmed
   memory. Measure CER, field F1, correction rate and latency on public/synthetic
   reports.
2. Voice -> local ASR -> timestamp locator -> review. Measure CER/WER, downstream
   extraction and real-time factor.

Original bytes, MIME type, hash, extraction engine/version, and locator must be
stored. OCR/ASR output never enters canonical memory without review.

## P2: sharing, summaries and operations

- One-page doctor summary labelled “family-prepared, not an official medical
  record,” with update time, unresolved items and source links.
- Reminder/check-in worker with timezone, recurrence, restart catch-up,
  idempotent delivery, skip/snooze and retry semantics.
- One-command local install/start, startup self-check, disk-space warning,
  upgrade-before-backup, rollback and recovery UI.
- Optional family sharing only after authentication, consent, revocation and
  audit are complete.

FHIR remains an adapter, not the internal schema. In R4 a document Bundle must
place `Composition` first, while `DocumentReference` represents document metadata
and attachments. See [FHIR R4 Bundle](https://hl7.org/fhir/R4/bundle.html) and
[FHIR R4 DocumentReference](https://hl7.org/fhir/R4/documentreference.html).
Run the official [FHIR validation workflow](https://hl7.org/fhir/R4/validation.html)
before claiming standards conformance.

## Regulatory product boundary

Keep intended use at organization, recall, communication preparation and
predefined safety escalation. Do not claim diagnosis, individualized treatment,
dosage changes, “no need to seek care,” or replacement of clinical judgment.

Health Canada distinguishes ordinary EHR storage/management from components with
a diagnostic or treatment purpose; those components may be medical devices:
[Health Canada EHR notice](https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/legislation-guidelines/electronic-health-record-product-notice-2022.html).
The FDA's 2026 CDS guidance similarly makes intended function and user context
central to the boundary:
[FDA Clinical Decision Support Software](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software).

These are engineering and product-risk references, not jurisdiction-specific
legal advice. Obtain local privacy and medical-device classification review
before commercial release or accepting real users.

## Flagship portfolio release gate

Before calling this the strongest resume project, publish a clean synthetic-only
v0.2 release containing:

- one-command clean-clone run and CI;
- architecture diagram, threat model and privacy impact assessment;
- reproducible durability, restore, longitudinal-query, model and safety results;
- model/data/eval cards with stopped experiments and limitations;
- official FHIR Validator report;
- 3-5 minute demo: arbitrary synthetic capture -> provider failure recovery ->
  review -> v1/v2/undo -> restart -> provenance -> backup/restore;
- precise resume bullets linked to committed result artifacts.

The strongest interview moment is not “the LoRA was smarter.” It is: **the
system refused to promote a candidate that looked plausible but missed crisis
cases, while preserving a usable manual and deterministic product path.**
