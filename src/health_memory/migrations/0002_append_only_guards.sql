CREATE TRIGGER record_candidates_no_delete
BEFORE DELETE ON record_candidates BEGIN
    SELECT RAISE(ABORT, 'record_candidates are retained for review history');
END;

CREATE TRIGGER observations_no_update
BEFORE UPDATE ON observations BEGIN
    SELECT RAISE(ABORT, 'observations are version projections and append-only');
END;

CREATE TRIGGER observations_no_delete
BEFORE DELETE ON observations BEGIN
    SELECT RAISE(ABORT, 'observations are version projections and append-only');
END;

CREATE TRIGGER medication_events_no_update
BEFORE UPDATE ON medication_events BEGIN
    SELECT RAISE(ABORT, 'medication_events are version projections and append-only');
END;

CREATE TRIGGER medication_events_no_delete
BEFORE DELETE ON medication_events BEGIN
    SELECT RAISE(ABORT, 'medication_events are version projections and append-only');
END;

CREATE TRIGGER symptom_events_no_update
BEFORE UPDATE ON symptom_events BEGIN
    SELECT RAISE(ABORT, 'symptom_events are version projections and append-only');
END;

CREATE TRIGGER symptom_events_no_delete
BEFORE DELETE ON symptom_events BEGIN
    SELECT RAISE(ABORT, 'symptom_events are version projections and append-only');
END;

CREATE TRIGGER appointments_no_update
BEFORE UPDATE ON appointments BEGIN
    SELECT RAISE(ABORT, 'appointments are version projections and append-only');
END;

CREATE TRIGGER appointments_no_delete
BEFORE DELETE ON appointments BEGIN
    SELECT RAISE(ABORT, 'appointments are version projections and append-only');
END;

CREATE TRIGGER idempotency_keys_no_update
BEFORE UPDATE ON idempotency_keys BEGIN
    SELECT RAISE(ABORT, 'idempotency results are immutable');
END;

CREATE TRIGGER idempotency_keys_no_delete
BEFORE DELETE ON idempotency_keys BEGIN
    SELECT RAISE(ABORT, 'idempotency results are immutable');
END;
