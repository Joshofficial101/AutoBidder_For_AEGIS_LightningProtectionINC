from __future__ import annotations

import argparse
from pathlib import Path

from src.database.db_connector import DBConnector


def _print_status() -> int:
    status = DBConnector.migration_status()
    print(f"Database path: {DBConnector.DB_PATH}")
    print(f"Backup dir: {DBConnector.BACKUP_DIR}")
    print(f"Applied migrations ({len(status['applied'])}): {status['applied']}")
    print(f"Pending migrations ({len(status['pending'])}): {status['pending']}")
    return 0


def _run_migrate() -> int:
    before = DBConnector.migration_status()
    db = DBConnector()
    db.close()
    after = DBConnector.migration_status()

    applied_now = [migration_id for migration_id in after["applied"] if migration_id not in before["applied"]]
    print(f"Applied migrations now: {applied_now}")
    print(f"Remaining pending: {after['pending']}")
    return 0


def _run_backup(reason: str) -> int:
    backup_path: Path = DBConnector.create_backup(reason=reason)
    print(f"Backup created: {backup_path}")
    return 0


def _run_rollback(steps: int) -> int:
    rolled_back = DBConnector.rollback_last_migrations(steps=steps)
    print(f"Rolled back migrations: {rolled_back}")
    remaining = DBConnector.migration_status()
    print(f"Pending after rollback: {remaining['pending']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LightningBid SQLite maintenance utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show migration status.")
    subparsers.add_parser("migrate", help="Apply pending migrations.")

    backup_parser = subparsers.add_parser("backup", help="Create a manual backup.")
    backup_parser.add_argument(
        "--reason",
        default="manual",
        help="Reason label included in backup filename.",
    )

    rollback_parser = subparsers.add_parser("rollback", help="Rollback the latest migration(s).")
    rollback_parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="Number of migrations to rollback (default: 1).",
    )

    args = parser.parse_args()
    if args.command == "status":
        return _print_status()
    if args.command == "migrate":
        return _run_migrate()
    if args.command == "backup":
        return _run_backup(reason=args.reason)
    if args.command == "rollback":
        return _run_rollback(steps=args.steps)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
