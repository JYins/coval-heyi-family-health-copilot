DROP TRIGGER source_capture_identity_guard;
DROP TRIGGER source_capture_no_delete;

ALTER TABLE source_capture_states RENAME TO source_capture_states_v5;

CREATE TABLE source_capture_states (
    source_artifact_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('captured', 'processing', 'failed_retryable', 'needs_review', 'rejected', 'completed')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error_code TEXT,
    record_id TEXT,
    lease_token TEXT,
    lease_expires_at TEXT,
    last_attempt_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (record_id, member_id)
        REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    UNIQUE (source_artifact_id, member_id)
);

INSERT INTO source_capture_states
    (source_artifact_id, member_id, status, attempt_count, last_error_code,
     record_id, last_attempt_at, created_at, updated_at)
SELECT
    source_artifact_id,
    member_id,
    CASE status WHEN 'failed' THEN 'failed_retryable' ELSE status END,
    attempt_count,
    last_error_code,
    record_id,
    last_attempt_at,
    created_at,
    updated_at
FROM source_capture_states_v5;

DROP TABLE source_capture_states_v5;

CREATE INDEX idx_capture_states_member_status
ON source_capture_states(member_id, status, updated_at DESC);

CREATE TRIGGER source_capture_identity_guard
BEFORE UPDATE ON source_capture_states
WHEN NEW.source_artifact_id <> OLD.source_artifact_id
  OR NEW.member_id <> OLD.member_id
  OR (OLD.record_id IS NOT NULL AND COALESCE(NEW.record_id, '') <> OLD.record_id)
BEGIN
    SELECT RAISE(ABORT, 'capture identity and linked record are immutable');
END;

CREATE TRIGGER source_capture_no_delete
BEFORE DELETE ON source_capture_states BEGIN
    SELECT RAISE(ABORT, 'capture lifecycle history is retained');
END;
