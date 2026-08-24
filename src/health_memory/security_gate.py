from __future__ import annotations

import sqlite3
from typing import Any


REAL_DATA_BLOCKERS = (
    "database_at_rest_encryption_not_configured",
    "os_keystore_and_recovery_drill_not_configured",
    "authenticated_same_origin_session_not_configured",
    "encrypted_authenticated_backup_not_configured",
    "verified_purge_and_packaged_runtime_not_configured",
)


def sqlite_wal_fix_present(version: str | None = None) -> bool:
    """Return whether the runtime includes the 2026 SQLite WAL-reset fix."""

    parts = tuple(int(item) for item in (version or sqlite3.sqlite_version).split("."))
    normalized = (parts + (0, 0, 0))[:3]
    if normalized >= (3, 51, 3):
        return True
    if normalized[:2] == (3, 50) and normalized >= (3, 50, 7):
        return True
    if normalized[:2] == (3, 44) and normalized >= (3, 44, 6):
        return True
    return False


def real_data_gate() -> dict[str, Any]:
    blockers = list(REAL_DATA_BLOCKERS)
    if not sqlite_wal_fix_present():
        blockers.append("sqlite_runtime_missing_2026_wal_reset_fix")
    return {
        "gate_enforced": True,
        "real_data_enabled": False,
        "ready": False,
        "mode": "synthetic_public_only",
        "sqlite_version": sqlite3.sqlite_version,
        "sqlite_wal_fix_present": sqlite_wal_fix_present(),
        "blockers": blockers,
    }


def parse_real_data_mode(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    raise RuntimeError(
        "COVAL_REAL_DATA_MODE must be one of: false/0/no/off or true/1/yes/on"
    )


def require_real_data_disabled(requested: bool) -> None:
    if requested:
        blockers = ", ".join(real_data_gate()["blockers"])
        raise RuntimeError(
            "Real-data mode is fail-closed until the security gate passes: " + blockers
        )
