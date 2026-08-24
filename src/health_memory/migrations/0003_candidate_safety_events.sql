CREATE TABLE candidate_safety_events (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL,
    safety_state TEXT NOT NULL CHECK (safety_state IN ('passed', 'refused', 'escalated', 'unknown')),
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    unsafe_request_detected INTEGER NOT NULL CHECK (unsafe_request_detected IN (0, 1)),
    forbidden_advice_generated INTEGER NOT NULL CHECK (forbidden_advice_generated = 0),
    origin TEXT NOT NULL CHECK (origin IN ('machine', 'carried_forward')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (record_id, member_id)
        REFERENCES health_records(id, member_id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_id, record_id)
        REFERENCES record_candidates(id, record_id) ON DELETE RESTRICT,
    FOREIGN KEY (source_artifact_id, member_id)
        REFERENCES source_artifacts(id, member_id) ON DELETE RESTRICT,
    UNIQUE (candidate_id)
);

INSERT INTO candidate_safety_events
    (id, member_id, record_id, candidate_id, source_artifact_id,
     safety_state, category, message, unsafe_request_detected,
     forbidden_advice_generated, origin, created_at)
SELECT
    lower(hex(randomblob(16))),
    member_id,
    record_id,
    id,
    source_artifact_id,
    json_extract(payload_json, '$.safety.state'),
    json_extract(payload_json, '$.safety.category'),
    json_extract(payload_json, '$.safety.message'),
    COALESCE(json_extract(payload_json, '$.safety.unsafe_request_detected'), 0),
    0,
    CASE WHEN validation_state = 'machine_candidate' THEN 'machine' ELSE 'carried_forward' END,
    created_at
FROM record_candidates;

CREATE TRIGGER candidate_safety_events_no_update
BEFORE UPDATE ON candidate_safety_events BEGIN
    SELECT RAISE(ABORT, 'candidate_safety_events are append-only');
END;

CREATE TRIGGER candidate_safety_events_no_delete
BEFORE DELETE ON candidate_safety_events BEGIN
    SELECT RAISE(ABORT, 'candidate_safety_events are append-only');
END;
