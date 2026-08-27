from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class ClosingConnection(sqlite3.Connection):
    """Commit or roll back like sqlite3, then release the Windows file handle."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30.0, factory=ClosingConnection)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    except Exception:
        connection.close()
        raise


def apply_migrations(database_path: Path) -> int:
    _enable_wal(database_path)
    _create_migration_ledger(database_path)

    for migration_path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = int(migration_path.name.split("_", 1)[0])
        sql = migration_path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        _apply_one(database_path, version, migration_path.name, checksum, sql)

    return schema_version(database_path)


def _apply_one(database_path: Path, version: int, name: str, checksum: str, sql: str) -> None:
    connection = connect(database_path)
    requires_foreign_keys_off = "-- coval: foreign_keys_off" in sql
    try:
        if requires_foreign_keys_off:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("PRAGMA legacy_alter_table = ON")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT name, checksum FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if row:
            if row["name"] != name or row["checksum"] != checksum:
                raise RuntimeError(
                    f"Migration {version} changed after application: {row['name']}"
                )
            connection.commit()
            return

        _execute_statements(connection, sql)
        if requires_foreign_keys_off:
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_rows:
                raise RuntimeError(
                    f"Migration {version} created {len(foreign_key_rows)} foreign-key errors"
                )
        connection.execute(
            """
            INSERT INTO schema_migrations(version, name, checksum, applied_at)
            VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (version, name, checksum),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if requires_foreign_keys_off:
            connection.execute("PRAGMA legacy_alter_table = OFF")
            connection.execute("PRAGMA foreign_keys = ON")
        connection.close()


def _enable_wal(database_path: Path) -> None:
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(10):
        connection = connect(database_path)
        try:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise RuntimeError(f"Could not enable SQLite WAL mode: {mode}")
            return
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).lower():
                raise
            last_error = error
            time.sleep(0.05 * (attempt + 1))
        finally:
            connection.close()
    raise RuntimeError("Could not initialize SQLite WAL mode after retries") from last_error


def _create_migration_ledger(database_path: Path) -> None:
    connection = connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _execute_statements(connection: sqlite3.Connection, sql: str) -> None:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if not sqlite3.complete_statement(buffer):
            continue
        statement = buffer.strip()
        buffer = ""
        if statement:
            connection.execute(statement)
    if buffer.strip():
        raise RuntimeError("Migration contains an incomplete SQL statement")


def schema_version(database_path: Path) -> int:
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
    return int(row["version"])


def latest_supported_schema_version() -> int:
    versions = [
        int(path.name.split("_", 1)[0])
        for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")
    ]
    return max(versions, default=0)


def validate_migration_history(database_path: Path) -> int:
    local_migrations: dict[int, tuple[str, str]] = {}
    for migration_path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"):
        version = int(migration_path.name.split("_", 1)[0])
        sql = migration_path.read_text(encoding="utf-8")
        local_migrations[version] = (
            migration_path.name,
            hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        )
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    applied_version = max((int(row["version"]) for row in rows), default=0)
    applied_versions = {int(row["version"]) for row in rows}
    unknown_versions = sorted(applied_versions - set(local_migrations))
    if unknown_versions:
        raise RuntimeError(f"Unsupported future schema migration: {unknown_versions}")
    expected_prefix = {
        version for version in local_migrations if version <= applied_version
    }
    if applied_versions != expected_prefix:
        missing = sorted(expected_prefix - applied_versions)
        unexpected = sorted(applied_versions - expected_prefix)
        raise RuntimeError(
            f"Migration history is not a complete supported prefix; "
            f"missing={missing}, unexpected={unexpected}"
        )
    for row in rows:
        expected = local_migrations.get(int(row["version"]))
        if expected is None:
            raise RuntimeError(f"Unsupported future schema migration: {row['version']}")
        if (row["name"], row["checksum"]) != expected:
            raise RuntimeError(f"Migration history mismatch at version {row['version']}")
    return applied_version


def integrity_report(database_path: Path) -> dict[str, object]:
    with connect(database_path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "integrity": integrity,
        "foreign_key_errors": len(foreign_key_rows),
    }
