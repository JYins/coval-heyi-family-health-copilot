from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .database import (
    apply_migrations,
    connect,
    integrity_report,
    latest_supported_schema_version,
    schema_version,
    validate_migration_history,
)
from .fhir_export import FHIR_VERSION, export_member_document


VAULT_FORMAT = "coval-health-vault"
VAULT_FORMAT_VERSION = 1
DATABASE_ENTRY = "database.sqlite"
MANIFEST_ENTRY = "manifest.json"
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_ENTRY_BYTES = 8 * 1024 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 64 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000


class VaultError(RuntimeError):
    pass


def create_backup(database_path: Path, output_path: Path, *, overwrite: bool = False) -> dict[str, Any]:
    database_path = Path(database_path).resolve()
    output_path = Path(output_path).resolve()
    if not database_path.is_file():
        raise VaultError(f"Database does not exist: {database_path}")
    protected_paths = {
        database_path,
        Path(f"{database_path}-wal").resolve(),
        Path(f"{database_path}-shm").resolve(),
    }
    if output_path in protected_paths:
        raise VaultError("Backup output must not replace the database or its WAL files")
    if output_path.exists() and not overwrite:
        raise VaultError(f"Backup already exists: {output_path}")
    _require_healthy_database(database_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="coval-vault-") as temp_name:
        stage = Path(temp_name)
        snapshot = stage / DATABASE_ENTRY
        _sqlite_snapshot(database_path, snapshot)
        _require_healthy_database(snapshot)

        payload_files: dict[str, Path] = {DATABASE_ENTRY: snapshot}
        with connect(snapshot) as connection:
            member_ids = [
                row["id"]
                for row in connection.execute("SELECT id FROM family_members ORDER BY id").fetchall()
            ]
        for member_id in member_ids:
            export_path = stage / "exports" / "fhir-r4" / _member_filename(member_id)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(
                json.dumps(
                    export_member_document(snapshot, member_id),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            payload_files[export_path.relative_to(stage).as_posix()] = export_path

        manifest = {
            "format": VAULT_FORMAT,
            "format_version": VAULT_FORMAT_VERSION,
            "created_at": _utc_now(),
            "schema_version": schema_version(snapshot),
            "fhir_version": FHIR_VERSION,
            "database_entry": DATABASE_ENTRY,
            "member_count": len(member_ids),
            "privacy": "contains_sensitive_health_data",
            "encryption": "none",
            "authenticity": "unsigned",
            "warning": (
                "Unencrypted and unsigned: hashes detect accidental corruption only. "
                "Synthetic/public demo data only; do not store real family or patient data."
            ),
            "files": {
                name: {"sha256": _sha256_file(path), "bytes": path.stat().st_size}
                for name, path in sorted(payload_files.items())
            },
        }
        manifest_path = stage / MANIFEST_ENTRY
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        temporary_output = _temporary_sibling(output_path)
        try:
            with zipfile.ZipFile(
                temporary_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                archive.write(manifest_path, MANIFEST_ENTRY)
                for name, path in sorted(payload_files.items()):
                    archive.write(path, name)
            verify_backup(temporary_output)
            _install_temporary(temporary_output, output_path, overwrite=overwrite)
        finally:
            temporary_output.unlink(missing_ok=True)
    return {**manifest, "archive": str(output_path)}


def verify_backup(archive_path: Path) -> dict[str, Any]:
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise VaultError(f"Backup does not exist: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest = _verify_open_archive(archive)
    except VaultError:
        raise
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise VaultError(f"Invalid backup archive: {error}") from error
    return {**manifest, "archive": str(archive_path), "verified": True}


def restore_backup(archive_path: Path, database_path: Path) -> dict[str, Any]:
    archive_path = Path(archive_path).resolve()
    database_path = Path(database_path).resolve()
    if not archive_path.is_file():
        raise VaultError(f"Backup does not exist: {archive_path}")
    if database_path.exists():
        raise VaultError(
            f"Restore target already exists: {database_path}. Restore into a clean path."
        )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_database = _temporary_sibling(database_path)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest = _verify_open_archive(archive)
            with archive.open(manifest["database_entry"], "r") as source:
                with temporary_database.open("wb") as target:
                    shutil.copyfileobj(source, target)
        apply_migrations(temporary_database)
        _require_healthy_database(temporary_database)
        _install_temporary(temporary_database, database_path, overwrite=False)
    except VaultError:
        raise
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise VaultError(f"Invalid backup archive: {error}") from error
    finally:
        temporary_database.unlink(missing_ok=True)
    return {
        "restored_database": str(database_path),
        "schema_version": schema_version(database_path),
        "integrity": integrity_report(database_path),
    }


def export_fhir(database_path: Path, output_dir: Path, *, overwrite: bool = False) -> dict[str, Any]:
    database_path = Path(database_path).resolve()
    output_dir = Path(output_dir).resolve()
    _require_healthy_database(database_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        member_ids = [
            row["id"] for row in connection.execute("SELECT id FROM family_members ORDER BY id")
        ]
    files: list[dict[str, Any]] = []
    for member_id in member_ids:
        target = output_dir / _member_filename(member_id)
        if target.resolve().parent != output_dir:
            raise VaultError(f"Unsafe family member export path: {member_id}")
        if target.exists() and not overwrite:
            raise VaultError(f"FHIR export already exists: {target}")
        temporary_target = _temporary_sibling(target)
        try:
            temporary_target.write_text(
                json.dumps(
                    export_member_document(database_path, member_id),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            _install_temporary(temporary_target, target, overwrite=overwrite)
        finally:
            temporary_target.unlink(missing_ok=True)
        files.append({"member_id": member_id, "path": str(target), "sha256": _sha256_file(target)})
    return {"fhir_version": FHIR_VERSION, "files": files}


def _sqlite_snapshot(source_path: Path, target_path: Path) -> None:
    source = sqlite3.connect(source_path, timeout=30.0)
    target = sqlite3.connect(target_path, timeout=30.0)
    try:
        source.execute("PRAGMA busy_timeout = 30000")
        source.backup(target)
    finally:
        target.close()
        source.close()


def _require_healthy_database(database_path: Path) -> None:
    report = integrity_report(database_path)
    if report != {"integrity": "ok", "foreign_key_errors": 0}:
        raise VaultError(f"Database integrity check failed: {report}")
    try:
        applied_version = validate_migration_history(database_path)
    except RuntimeError as error:
        raise VaultError(str(error)) from error
    if applied_version > latest_supported_schema_version():
        raise VaultError(f"Unsupported future schema version: {applied_version}")


def _verify_open_archive(archive: zipfile.ZipFile) -> dict[str, Any]:
    names = archive.namelist()
    if len(names) > MAX_ARCHIVE_FILES:
        raise VaultError("Backup contains too many entries")
    if len(names) != len(set(names)):
        raise VaultError("Backup contains duplicate entries")
    total_size = 0
    for info in archive.infolist():
        if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
            raise VaultError(f"Backup entry is too large: {info.filename}")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_TOTAL_BYTES:
            raise VaultError("Backup expands beyond the supported size limit")
        if info.file_size and info.compress_size == 0:
            raise VaultError(f"Invalid compressed size for {info.filename}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise VaultError(f"Suspicious compression ratio for {info.filename}")
    for name in names:
        _validate_archive_name(name)
    if MANIFEST_ENTRY not in names:
        raise VaultError("Backup manifest is missing")
    manifest = json.loads(archive.read(MANIFEST_ENTRY).decode("utf-8"))
    _validate_manifest(manifest)
    expected_names = {MANIFEST_ENTRY, *manifest["files"].keys()}
    if set(names) != expected_names:
        raise VaultError("Backup entries do not match the manifest")
    for name, metadata in manifest["files"].items():
        digest = hashlib.sha256()
        byte_count = 0
        with archive.open(name, "r") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
        if digest.hexdigest() != metadata["sha256"] or byte_count != metadata["bytes"]:
            raise VaultError(f"Backup integrity check failed for {name}")

    with tempfile.TemporaryDirectory(prefix="coval-vault-verify-") as temp_name:
        database_copy = Path(temp_name) / DATABASE_ENTRY
        with archive.open(manifest["database_entry"], "r") as source:
            with database_copy.open("wb") as target:
                shutil.copyfileobj(source, target)
        _require_healthy_database(database_copy)
        actual_schema = schema_version(database_copy)
        if actual_schema != manifest["schema_version"]:
            raise VaultError(
                f"Schema mismatch: manifest={manifest['schema_version']} database={actual_schema}"
            )
        try:
            apply_migrations(database_copy)
        except Exception as error:
            raise VaultError(f"Backup database cannot migrate during restore drill: {error}") from error
        _require_healthy_database(database_copy)
    return manifest


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise VaultError("Backup manifest root must be an object")
    if manifest.get("format") != VAULT_FORMAT:
        raise VaultError("Unsupported backup format")
    if manifest.get("format_version") != VAULT_FORMAT_VERSION:
        raise VaultError(f"Unsupported backup format version: {manifest.get('format_version')}")
    if manifest.get("database_entry") != DATABASE_ENTRY:
        raise VaultError("Unsupported database entry")
    if manifest.get("encryption") != "none":
        raise VaultError("This build cannot restore encrypted archives yet")
    files = manifest.get("files")
    if not isinstance(files, dict) or DATABASE_ENTRY not in files:
        raise VaultError("Backup file manifest is invalid")
    for name, metadata in files.items():
        _validate_archive_name(name)
        if not isinstance(metadata, dict):
            raise VaultError(f"Invalid metadata for {name}")
        digest = metadata.get("sha256")
        byte_count = metadata.get("bytes")
        if not isinstance(digest, str) or len(digest) != 64:
            raise VaultError(f"Invalid SHA-256 for {name}")
        if not isinstance(byte_count, int) or byte_count < 0:
            raise VaultError(f"Invalid byte count for {name}")


def _validate_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise VaultError(f"Unsafe backup entry: {name}")


def _member_filename(member_id: object) -> str:
    value = str(member_id)
    if not value or len(value) > 64 or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        for character in value
    ):
        raise VaultError(f"Unsafe family member id for export: {value!r}")
    return f"{value}.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _temporary_sibling(path: Path) -> Path:
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary_path = Path(name)
    try:
        os.chmod(temporary_path, 0o600)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise VaultError(f"Could not secure temporary private file: {error}") from error
    return temporary_path


def _install_temporary(temporary_path: Path, target_path: Path, *, overwrite: bool) -> None:
    if overwrite:
        os.replace(temporary_path, target_path)
        return
    try:
        os.link(temporary_path, target_path)
    except FileExistsError as error:
        raise VaultError(f"Target already exists: {target_path}") from error
    except OSError as error:
        raise VaultError(f"Could not install target without overwriting it: {error}") from error
    temporary_path.unlink()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
