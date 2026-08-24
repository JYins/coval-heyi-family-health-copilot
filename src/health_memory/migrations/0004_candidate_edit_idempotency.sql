DROP TRIGGER idempotency_keys_no_update;
DROP TRIGGER idempotency_keys_no_delete;

-- Older candidate-edit rows stored only the mutable health-record ID, so they
-- cannot prove which candidate the client reviewed. Invalidate only those
-- ambiguous development-era keys rather than replaying the wrong revision.
DELETE FROM idempotency_keys
WHERE operation = 'candidate_edit' AND resource_type = 'health_record';

CREATE TRIGGER idempotency_keys_no_update
BEFORE UPDATE ON idempotency_keys BEGIN
    SELECT RAISE(ABORT, 'idempotency results are immutable');
END;

CREATE TRIGGER idempotency_keys_no_delete
BEFORE DELETE ON idempotency_keys BEGIN
    SELECT RAISE(ABORT, 'idempotency results are immutable');
END;
