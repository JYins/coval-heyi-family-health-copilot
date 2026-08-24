-- A database briefly used with schema v5 could contain `processing` without a
-- token because leases did not exist yet. Make that state recoverable.
UPDATE source_capture_states
SET status = 'failed_retryable',
    last_error_code = 'lease_missing_after_migration',
    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE status = 'processing'
  AND (lease_token IS NULL OR lease_expires_at IS NULL);

CREATE TRIGGER source_capture_processing_requires_lease_insert
BEFORE INSERT ON source_capture_states
WHEN NEW.status = 'processing'
 AND (NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'processing capture requires a lease');
END;

CREATE TRIGGER source_capture_processing_requires_lease_update
BEFORE UPDATE ON source_capture_states
WHEN NEW.status = 'processing'
 AND (NEW.lease_token IS NULL OR NEW.lease_expires_at IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'processing capture requires a lease');
END;

CREATE TRIGGER source_capture_nonprocessing_clears_lease
BEFORE UPDATE ON source_capture_states
WHEN NEW.status <> 'processing'
 AND (NEW.lease_token IS NOT NULL OR NEW.lease_expires_at IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'non-processing capture cannot retain a lease');
END;
