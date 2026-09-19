"""
V3 Milestone 2 Phase 2: Database Migration CLI.

Command-line interface for executing SQLite -> PostgreSQL migration
and legacy schema reconciliation.

Usage examples:
    python -m app.db.cli migrate \\
        --sqlite-path ./learnflow.db \\
        --postgres-url postgresql://user:pass@localhost:5432/learnflow \\
        --target-user-email user@example.com

    python -m app.db.cli migrate \\
        --sqlite-path ./learnflow.db \\
        --postgres-url postgresql://user:pass@localhost:5432/learnflow \\
        --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import settings
from app.db.sqlite_to_postgres import (
    MigrationError,
    migrate_sqlite_to_postgres,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.db.cli",
        description="LearnFlow V3 Database Migration CLI (SQLite -> PostgreSQL)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'migrate' subcommand
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate learning data from a source SQLite database into target PostgreSQL.",
    )
    _add_migrate_arguments(migrate_parser)

    # Also add arguments to root parser so running without the 'migrate' subcommand works directly:
    # e.g. python -m app.db.cli --sqlite-path ...
    _add_migrate_arguments(parser)

    return parser


def _add_migrate_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sqlite-path",
        dest="sqlite_path",
        default="./learnflow.db",
        help="Path to the source SQLite database file (default: ./learnflow.db).",
    )
    parser.add_argument(
        "--postgres-url",
        dest="postgres_url",
        default=None,
        help="Connection URL for the target PostgreSQL database (e.g. postgresql://user:pass@host:5432/db).",
    )
    parser.add_argument(
        "--target-user-email",
        dest="target_user_email",
        default=None,
        help="Email of the target registered user who will own legacy V2.4 application data.",
    )
    parser.add_argument(
        "--target-user-id",
        dest="target_user_id",
        default=None,
        help="ID of the target registered user who will own legacy V2.4 application data.",
    )
    parser.add_argument(
        "--source-storage-dir",
        dest="source_storage_dir",
        default=None,
        help="Path to directory containing source physical document files (defaults to backend/uploads).",
    )
    parser.add_argument(
        "--target-storage-dir",
        dest="target_storage_dir",
        default=None,
        help="Path to target storage directory for physical document files (defaults to backend/uploads).",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Simulate the migration and validate source data without modifying target database or storage.",
    )


def run_cli(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    # Resolve target postgres URL
    postgres_url = args.postgres_url
    if not postgres_url:
        # Fall back to settings.database_url if not sqlite
        if settings.database_url and not settings.database_url.startswith("sqlite"):
            postgres_url = settings.database_url
        else:
            sys.stderr.write(
                "Error: --postgres-url is required (or DATABASE_URL must be configured with a PostgreSQL URL).\n"
            )
            return 1

    try:
        summary = migrate_sqlite_to_postgres(
            sqlite_path=args.sqlite_path,
            postgres_url=postgres_url,
            target_user_id=args.target_user_id,
            target_user_email=args.target_user_email,
            source_storage_dir=args.source_storage_dir,
            target_storage_dir=args.target_storage_dir,
            dry_run=args.dry_run,
        )
        print(summary.format_report())
        return 0
    except MigrationError as exc:
        sys.stderr.write(f"\nMigration Error: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"\nUnexpected Error during migration: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())
