CREATE TABLE family_members (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    relation TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0 AND age <= 130),
    profile TEXT NOT NULL DEFAULT '',
    badges_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(badges_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (id, id)
);

CREATE TABLE source_artifacts (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('text', 'ocr', 'voice', 'blood_pressure')),
    source_label TEXT NOT NULL,
    original_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
    declared_event_date TEXT,
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_locator_json)),
    captured_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    UNIQUE (id, member_id),
    UNIQUE (member_id, artifact_kind, content_sha256, declared_event_date)
);

CREATE TABLE ingestion_jobs (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('needs_review', 'completed', 'failed')),
    provider TEXT NOT NULL,
    model_ref TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    error_code TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    UNIQUE (id, member_id),
    UNIQUE (source_artifact_id, extraction_version)
);

CREATE TABLE health_records (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    ingestion_job_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'approved', 'archived')),
    current_candidate_id TEXT,
    current_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (ingestion_job_id, member_id)
        REFERENCES ingestion_jobs(id, member_id) ON DELETE RESTRICT,
    UNIQUE (id, member_id),
    UNIQUE (ingestion_job_id)
);

CREATE TABLE record_candidates (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    ingestion_job_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'superseded')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    extraction_version TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL CHECK (validation_state IN ('machine_candidate', 'user_edited', 'user_confirmed')),
    edited_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    FOREIGN KEY (record_id, member_id)
        REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (ingestion_job_id, member_id)
        REFERENCES ingestion_jobs(id, member_id) ON DELETE RESTRICT,
    UNIQUE (id, record_id),
    UNIQUE (record_id, revision)
);

CREATE TABLE record_versions (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    parent_version_id TEXT,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    operation TEXT NOT NULL CHECK (operation IN ('approve', 'edit', 'undo')),
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
    snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
    extraction_version TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL CHECK (validation_state = 'user_confirmed'),
    edit_reason TEXT NOT NULL,
    edited_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id)
        REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_id, record_id)
        REFERENCES record_candidates(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_version_id) REFERENCES record_versions(id) ON DELETE RESTRICT,
    UNIQUE (id, record_id),
    UNIQUE (record_id, version_number)
);

CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    name TEXT NOT NULL,
    value_text TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    observed_at TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL,
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_locator_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (version_id, record_id) REFERENCES record_versions(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE medication_events (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    medication_name TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('reported', 'started', 'stopped', 'missed', 'unknown')),
    dose_text TEXT NOT NULL DEFAULT '',
    occurred_at TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL,
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_locator_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (version_id, record_id) REFERENCES record_versions(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE symptom_events (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    symptom_text TEXT NOT NULL,
    onset_text TEXT NOT NULL DEFAULT '',
    negated INTEGER NOT NULL DEFAULT 0 CHECK (negated IN (0, 1)),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL,
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_locator_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (version_id, record_id) REFERENCES record_versions(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE appointments (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    appointment_text TEXT NOT NULL,
    scheduled_at TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    validation_state TEXT NOT NULL,
    source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_locator_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (version_id, record_id) REFERENCES record_versions(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE reminders (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT,
    source_artifact_id TEXT,
    reminder_kind TEXT NOT NULL,
    due_at TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'completed', 'cancelled', 'failed')),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE safety_events (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    safety_state TEXT NOT NULL CHECK (safety_state IN ('passed', 'refused', 'escalated', 'unknown')),
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    unsafe_request_detected INTEGER NOT NULL CHECK (unsafe_request_detected IN (0, 1)),
    forbidden_advice_generated INTEGER NOT NULL CHECK (forbidden_advice_generated = 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (version_id, record_id) REFERENCES record_versions(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT,
    source_artifact_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details_json)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, member_id) REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id) REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT
);

CREATE TABLE idempotency_keys (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (member_id) REFERENCES family_members(id) ON DELETE RESTRICT,
    UNIQUE (member_id, operation, idempotency_key)
);

CREATE INDEX idx_health_records_member_status ON health_records(member_id, status);
CREATE INDEX idx_versions_record_number ON record_versions(record_id, version_number DESC);
CREATE INDEX idx_audit_record_created ON audit_events(record_id, created_at);

CREATE TRIGGER source_artifacts_no_update
BEFORE UPDATE ON source_artifacts BEGIN
    SELECT RAISE(ABORT, 'source_artifacts are immutable');
END;

CREATE TRIGGER source_artifacts_no_delete
BEFORE DELETE ON source_artifacts BEGIN
    SELECT RAISE(ABORT, 'source_artifacts are immutable');
END;

CREATE TRIGGER candidates_payload_immutable
BEFORE UPDATE ON record_candidates
WHEN NEW.payload_json <> OLD.payload_json
  OR NEW.payload_sha256 <> OLD.payload_sha256
  OR NEW.source_artifact_id <> OLD.source_artifact_id
  OR NEW.extraction_version <> OLD.extraction_version
BEGIN
    SELECT RAISE(ABORT, 'candidate payload is immutable; create a revision');
END;

CREATE TRIGGER record_versions_no_update
BEFORE UPDATE ON record_versions BEGIN
    SELECT RAISE(ABORT, 'record_versions are append-only');
END;

CREATE TRIGGER record_versions_no_delete
BEFORE DELETE ON record_versions BEGIN
    SELECT RAISE(ABORT, 'record_versions are append-only');
END;

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER safety_events_no_update
BEFORE UPDATE ON safety_events BEGIN
    SELECT RAISE(ABORT, 'safety_events are append-only');
END;

CREATE TRIGGER safety_events_no_delete
BEFORE DELETE ON safety_events BEGIN
    SELECT RAISE(ABORT, 'safety_events are append-only');
END;

CREATE TRIGGER health_records_candidate_head_guard
BEFORE UPDATE OF current_candidate_id ON health_records
WHEN NEW.current_candidate_id IS NOT NULL
 AND NOT EXISTS (
    SELECT 1 FROM record_candidates c
    WHERE c.id = NEW.current_candidate_id
      AND c.record_id = NEW.id
      AND c.member_id = NEW.member_id
 )
BEGIN
    SELECT RAISE(ABORT, 'candidate head must belong to record and member');
END;

CREATE TRIGGER health_records_version_head_guard
BEFORE UPDATE OF current_version_id ON health_records
WHEN NEW.current_version_id IS NOT NULL
 AND NOT EXISTS (
    SELECT 1 FROM record_versions v
    WHERE v.id = NEW.current_version_id
      AND v.record_id = NEW.id
      AND v.member_id = NEW.member_id
 )
BEGIN
    SELECT RAISE(ABORT, 'version head must belong to record and member');
END;
