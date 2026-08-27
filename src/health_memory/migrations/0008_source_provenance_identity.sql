-- coval: foreign_keys_off
-- Preserve separate evidence when identical content arrives from distinct
-- declared sources. Existing same-source content deduplication remains intact.

DROP TRIGGER source_artifacts_no_update;
DROP TRIGGER source_artifacts_no_delete;

ALTER TABLE source_artifacts RENAME TO source_artifacts_v7;

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
    UNIQUE (member_id, artifact_kind, source_label, content_sha256, declared_event_date)
);

INSERT INTO source_artifacts
    (id, member_id, artifact_kind, source_label, original_text,
     content_sha256, byte_length, declared_event_date, source_locator_json,
     captured_at, created_at)
SELECT
    id, member_id, artifact_kind, source_label, original_text,
    content_sha256, byte_length, declared_event_date, source_locator_json,
    captured_at, created_at
FROM source_artifacts_v7;

DROP TABLE source_artifacts_v7;

CREATE TRIGGER source_artifacts_no_update
BEFORE UPDATE ON source_artifacts BEGIN
    SELECT RAISE(ABORT, 'source_artifacts are immutable');
END;

CREATE TRIGGER source_artifacts_no_delete
BEFORE DELETE ON source_artifacts BEGIN
    SELECT RAISE(ABORT, 'source_artifacts are immutable');
END;
