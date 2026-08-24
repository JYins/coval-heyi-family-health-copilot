CREATE TABLE source_capture_states (
    source_artifact_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('captured', 'processing', 'failed', 'needs_review', 'rejected', 'completed')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error_code TEXT,
    record_id TEXT,
    last_attempt_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, member_id)
        REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    UNIQUE (source_artifact_id, member_id)
);

CREATE INDEX idx_capture_states_member_status
ON source_capture_states(member_id, status, updated_at DESC);

-- Existing databases already have a source -> record relationship. Backfill the
-- lifecycle without changing any immutable evidence or record history.
INSERT INTO source_capture_states
    (source_artifact_id, member_id, status, attempt_count, record_id,
     last_attempt_at, created_at, updated_at)
SELECT
    s.id,
    s.member_id,
    CASE r.status
        WHEN 'approved' THEN 'completed'
        WHEN 'archived' THEN 'rejected'
        ELSE 'needs_review'
    END,
    1,
    r.id,
    j.started_at,
    s.created_at,
    COALESCE(r.updated_at, s.created_at)
FROM source_artifacts s
JOIN health_records r ON r.source_artifact_id = s.id
JOIN ingestion_jobs j ON j.id = r.ingestion_job_id;

CREATE TRIGGER source_capture_identity_guard
BEFORE UPDATE ON source_capture_states
WHEN NEW.source_artifact_id <> OLD.source_artifact_id
  OR NEW.member_id <> OLD.member_id
  OR COALESCE(NEW.record_id, '') <> COALESCE(OLD.record_id, '')
     AND OLD.record_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'capture identity and linked record are immutable');
END;

CREATE TRIGGER source_capture_no_delete
BEFORE DELETE ON source_capture_states BEGIN
    SELECT RAISE(ABORT, 'capture lifecycle history is retained');
END;
