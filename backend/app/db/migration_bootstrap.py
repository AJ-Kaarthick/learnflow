"""
V3 Milestone 2 Phase 1: startup database bootstrap.

Before this phase, app/main.py called `Base.metadata.create_all(bind=engine)`
on every startup: "create any table that doesn't exist yet." That's an
adequate bootstrap for a schema that only ever grows new tables and is
never inspected for what state it's actually in, but it has two
problems this phase's brief specifically calls out:

  1. It cannot alter an existing table. If a model gains a new column
     (exactly what V3 Milestone 1 did to Document and Conversation,
     adding owner_type/owner_id, and to the schema as a whole, adding
     the User/UserSession identity tables), `create_all` silently does
     nothing to a `documents` table that already existed -- there's no
     migration step that would have added the column to a database
     created before that. Alembic, from this phase on, is what
     actually applies a schema change like that to an existing
     database.

  2. It has no record of "what schema state is this database at,"
     which is exactly what Phase 2's SQLite -> PostgreSQL migration
     needs to reason about cleanly.

This module is the bridge between the old world and the new one. It
runs once at startup (see app/main.py) and decides, from the
database's own actual state, which of FOUR situations it's in:

  - EMPTY database (no tables at all): a brand-new SQLite file, a
    brand-new PostgreSQL database, or -- most commonly today -- the
    fresh temporary SQLite file tests/conftest.py points DATABASE_URL
    at for every test session. Alembic has nothing to reconcile, so it
    just runs every migration from scratch (`upgrade head`), which
    creates the full current schema.

  - MANAGED database (already has an `alembic_version` table): a
    database this bootstrap (or a developer running `alembic upgrade
    head` by hand) has already adopted into the migration system on a
    previous run. Just apply any migrations newer than its current
    revision, same as any normal Alembic-managed project.

  - LEGACY, SCHEMA MATCHES CURRENT MODELS EXACTLY (application tables
    already exist, no `alembic_version` table, and every table/column
    the current models define is actually present): a pre-Alembic
    database -- created by the old `create_all`-based bootstrap --
    that genuinely already has the current schema (e.g. it was last
    touched right before this phase, when `create_all` had already
    kept it in sync). It's accurate to record this database as being
    at head, so it's *stamped* there without executing a single DDL
    statement. From the next startup on, it's indistinguishable from
    one that was always migration-managed.

  - LEGACY, INCOMPATIBLE (application tables already exist, no
    `alembic_version` table, but the schema does NOT fully match
    current models -- missing table(s) and/or missing column(s) on an
    existing table, e.g. a database that predates V3 Milestone 1's
    ownership fields and identity tables entirely): this is the case
    the original version of this module got wrong -- it would stamp
    this database at head anyway, which is a false claim ("this
    database already has the current schema") that Alembic would then
    trust on every later check, including whatever Phase 2's actual
    SQLite -> PostgreSQL migration needs to reason about. Instead:
    this database is left UNMANAGED (no `alembic_version` table is
    created, so this same check runs -- and reports -- again on every
    future startup until it's genuinely reconciled). Its existing data
    is not touched. Any table the project has added since this
    database was created is still created, via the same additive-only
    `create_all` this project's startup has always used for that --
    exactly the same non-destructive behavior this database would have
    seen every startup before this phase existed -- but no column is
    ever added to an already-existing table, and nothing is stamped.
    Reconciling this database with the current schema is explicitly
    left to V3 Milestone 2 Phase 2 (or a future targeted migration),
    not attempted here.

No case above ever drops, recreates, or destructively modifies a
table, or changes a single existing row.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db import models  # noqa: F401  (populates Base.metadata -- see below)
from app.db.database import Base

# Importing app.db.models is required, not incidental: it's what
# registers every model class's table onto Base.metadata. This module
# reads Base.metadata.tables directly (see _has_preexisting_application_tables
# and _compute_schema_drift below), so without this import, calling
# run_startup_migrations from a process that hadn't already imported
# the models elsewhere first would see an empty metadata object and
# misjudge every database as having no application tables at all.

logger = logging.getLogger(__name__)

# backend/app/db/migration_bootstrap.py -> parents[2] == backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI_PATH = _BACKEND_ROOT / "alembic.ini"


def _alembic_config() -> Config:
    """
    Builds an Alembic Config pointing at this project's alembic.ini.
    Script location / migration URL come from the ini file and
    alembic/env.py respectively (env.py reads the live
    settings.database_url itself -- see that file) -- nothing here
    needs to duplicate either.
    """
    return Config(str(_ALEMBIC_INI_PATH))


def _get_current_alembic_revision(engine: Engine) -> str | None:
    """
    Returns the revision id recorded in this database's
    `alembic_version` table, or None if that table doesn't exist yet
    (i.e. this database has never been touched by Alembic).
    """
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        return migration_context.get_current_heads()[0] if migration_context.get_current_heads() else None


def _has_alembic_version_table(engine: Engine) -> bool:
    return "alembic_version" in inspect(engine).get_table_names()


def _has_preexisting_application_tables(engine: Engine) -> bool:
    """
    True if any table this project's models define already exists in
    the database. Used to distinguish a genuinely empty/new database
    (safe to build via a normal `upgrade head`) from a pre-Alembic
    database created by the old `create_all` bootstrap (whose data
    must be preserved, not recreated -- see this module's docstring).
    """
    existing_tables = set(inspect(engine).get_table_names())
    model_tables = set(Base.metadata.tables.keys())
    return bool(existing_tables & model_tables)


@dataclass
class SchemaDrift:
    """
    The result of comparing a database's actual schema against what
    the current models (Base.metadata) define. Read-only: computing
    this never alters the database.
    """

    missing_tables: set[str] = field(default_factory=set)
    missing_columns: dict[str, set[str]] = field(default_factory=dict)

    @property
    def has_drift(self) -> bool:
        return bool(self.missing_tables or self.missing_columns)


def _compute_schema_drift(engine: Engine) -> SchemaDrift:
    """
    Compares every table/column the current models define against
    what actually exists in `engine`'s database, without altering
    anything. This is the single source of truth
    `run_startup_migrations` uses to decide whether a legacy database
    (see this module's docstring) may honestly be stamped at head, or
    whether it's genuinely incompatible and must be left unmanaged.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    drift = SchemaDrift()

    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            drift.missing_tables.add(table.name)
            continue

        actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
        expected_columns = {col.name for col in table.columns}
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            drift.missing_columns[table.name] = missing_columns

    return drift


def _log_exact_match_legacy_adoption() -> None:
    logger.warning(
        "Database has existing application tables but no Alembic history. "
        "Its schema was checked against the current models and matches "
        "exactly (no missing tables or columns), so it is being treated as "
        "a pre-migration database created by the previous create_all() "
        "bootstrap that already happened to be fully up to date: stamping "
        "it at the current head revision WITHOUT running any migration "
        "DDL, so its existing data is left completely untouched."
    )


def _log_incompatible_legacy_database(drift: SchemaDrift) -> None:
    logger.error(
        "Database has existing application tables that do NOT match the "
        "current models -- missing table(s): %s; missing column(s) on "
        "existing table(s): %s. This looks like a genuinely legacy schema "
        "(e.g. one created before V3 Milestone 1 introduced ownership "
        "fields and/or the guest/user identity tables). This database will "
        "NOT be stamped as Alembic head, since doing so would falsely "
        "record that it already has the current schema. It remains "
        "unmanaged by Alembic -- this same check will run, and report "
        "again, on every future startup -- until it is properly "
        "reconciled, which is intentionally left to V3 Milestone 2 Phase "
        "2's SQLite -> PostgreSQL migration (or an equivalent targeted "
        "migration), not performed here. No existing table has been "
        "altered, dropped, or had any row changed; any genuinely new "
        "table (one that doesn't exist in this database at all yet) is "
        "still created, the same additive-only way this project's startup "
        "has always created a new table -- but no column is added to a "
        "table that already exists.",
        sorted(drift.missing_tables) or "none",
        {table: sorted(columns) for table, columns in drift.missing_columns.items()} or "none",
    )


def run_startup_migrations(engine: Engine) -> None:
    """
    The single call site app/main.py uses in place of the old
    `Base.metadata.create_all(bind=engine)`. See this module's
    docstring for the four cases this distinguishes between.
    """
    alembic_cfg = _alembic_config()

    if _has_alembic_version_table(engine):
        # MANAGED: already adopted on a previous run (or by hand).
        # Normal path every Alembic-managed project uses.
        current_revision = _get_current_alembic_revision(engine)
        logger.info(
            "Database is already Alembic-managed (current revision: %s). "
            "Applying any pending migrations.",
            current_revision,
        )
        command.upgrade(alembic_cfg, "head")
        return

    if not _has_preexisting_application_tables(engine):
        # EMPTY: nothing to preserve. Build the schema the normal way,
        # by actually running every migration -- this is also what
        # makes the migration history itself get exercised on every
        # test run (see tests/conftest.py, which points DATABASE_URL
        # at a fresh, empty temporary SQLite file per test session)
        # rather than only ever being tested manually.
        logger.info("Database is empty. Running all migrations to build the current schema.")
        command.upgrade(alembic_cfg, "head")
        return

    # Has some pre-existing application tables but no Alembic history
    # yet. Whether it's honest to claim this database already matches
    # the current (head) schema must be checked BEFORE that claim is
    # ever recorded -- not assumed and corrected after the fact.
    drift = _compute_schema_drift(engine)

    if not drift.has_drift:
        # LEGACY, exact match: safe and accurate to stamp.
        _log_exact_match_legacy_adoption()
        command.stamp(alembic_cfg, "head")
        return

    # LEGACY, incompatible: do not stamp, do not run migrations (which
    # would try to CREATE TABLE statements against tables that already
    # partially exist). Preserve this project's pre-Alembic behavior
    # for exactly this case -- create_all() only ever creates tables
    # that don't exist yet, never alters one that does -- so this is
    # exactly as non-destructive as what ran here every startup before
    # this phase existed.
    _log_incompatible_legacy_database(drift)
    Base.metadata.create_all(bind=engine)
