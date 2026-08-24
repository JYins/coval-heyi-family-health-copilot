from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.health_memory.vault import (  # noqa: E402
    VaultError,
    create_backup,
    export_fhir,
    restore_backup,
    verify_backup,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "UNENCRYPTED, SYNTHETIC-ONLY: create, verify, restore, or export "
            "a local Coval Health demo vault. Never use real family/patient data."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Create a verified .coval backup archive.")
    backup.add_argument("--database", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--overwrite", action="store_true")
    backup.add_argument("--acknowledge-synthetic-only-unencrypted", action="store_true")

    verify = subparsers.add_parser("verify", help="Verify hashes and SQLite integrity.")
    verify.add_argument("--archive", type=Path, required=True)

    restore = subparsers.add_parser("restore", help="Restore into a new database path.")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--database", type=Path, required=True)
    restore.add_argument("--acknowledge-synthetic-only-unencrypted", action="store_true")

    export = subparsers.add_parser("export-fhir", help="Export approved current heads as FHIR R4.")
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    export.add_argument("--overwrite", action="store_true")
    export.add_argument("--acknowledge-synthetic-only-unencrypted", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command in {"backup", "restore", "export-fhir"} and not args.acknowledge_synthetic_only_unencrypted:
            raise VaultError(
                "Explicit --acknowledge-synthetic-only-unencrypted is required; "
                "this command must never receive real family/patient data"
            )
        if args.command == "backup":
            result = create_backup(args.database, args.output, overwrite=args.overwrite)
        elif args.command == "verify":
            result = verify_backup(args.archive)
        elif args.command == "restore":
            result = restore_backup(args.archive, args.database)
        else:
            result = export_fhir(args.database, args.output_dir, overwrite=args.overwrite)
    except VaultError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
