"""
V3 Milestone 2 Phase 1: PostgreSQL compatibility boundary.

Every other test in this suite (including tests/test_migrations.py)
runs against SQLite, since that's what this project's local
dev/test environment has always provided with zero setup. Phase 1's
brief is explicit that this isn't sufficient on its own: "Do not fake
PostgreSQL compatibility by only testing SQLite."

This module is the other half -- the same migration-framework
guarantees (a fresh database migrates to the exact current schema,
ownership columns survive, the migration is reversible), run against a
real PostgreSQL server instead of SQLite. It's what actually proves
`app/db/database.py`'s dialect-aware `build_engine`,
`alembic/env.py`'s per-dialect batch-mode handling, and the genesis
migration in alembic/versions/ produce a working schema on PostgreSQL,
not just a schema that *looks* portable by inspection.

THE TEST BOUNDARY:

These tests require a real, reachable PostgreSQL server and are opt-in
via the `POSTGRES_TEST_DATABASE_URL` environment variable (e.g.
`postgresql://user:password@localhost:5432/learnflow_test`) -- pointed
at a scratch database that is safe to create and drop tables in
repeatedly, never a real environment's data.

- `POSTGRES_TEST_DATABASE_URL` unset (the default -- true for this
  project's sandboxed dev/CI environment as of this phase, which has
  no PostgreSQL service running): every test below is skipped, with a
  clear reason explaining how to opt in. This is a deliberate,
  documented boundary, not a silent gap -- the full backend test count
  reported for this phase does not include these; see the phase report
  for how many were skipped and why.
- `POSTGRES_TEST_DATABASE_URL` set: tests run for real against that
  server. Every test that creates tables cleans them up afterward
  (drop_all in a fixture teardown) so the suite is safe to run
  repeatedly against a persistent scratch database.

Marked with the `postgres` marker (registered in pytest.ini) so a
future CI setup can select or deselect this file specifically (e.g.
`pytest -m "not postgres"` for a fast SQLite-only run, or a separate CI
job that sets `POSTGRES_TEST_DATABASE_URL` and runs `pytest -m postgres`).
"""

import os

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db import migration_bootstrap
from app.db.database import Base, build_engine, is_sqlite_url

pytestmark = pytest.mark.postgres

_POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

if not _POSTGRES_TEST_DATABASE_URL:
    pytest.skip(
        "PostgreSQL compatibility tests skipped: set POSTGRES_TEST_DATABASE_URL "
        "(e.g. postgresql://user:password@localhost:5432/learnflow_test) to a "
        "reachable, disposable PostgreSQL database to run them. This environment "
        "has no PostgreSQL service available, which is why the backend test "
        "count for this phase is reported separately from this file -- see the "
        "phase report.",
        allow_module_level=True,
    )

assert not is_sqlite_url(_POSTGRES_TEST_DATABASE_URL), (
    "POSTGRES_TEST_DATABASE_URL must point at a PostgreSQL database, not a "
    "SQLite one -- these tests exist specifically to cover what the SQLite "
    "suite in test_migrations.py cannot."
)

_EXPECTED_TABLES = set(Base.metadata.tables.keys())


@pytest.fixture()
def postgres_engine(monkeypatch):
    """
    Points settings.database_url (and therefore alembic/env.py) at the
    real PostgreSQL server for one test, builds an engine against it,
    and guarantees every table this test created is dropped afterward
    regardless of pass/fail -- so this suite is safe to run repeatedly
    against a persistent scratch database rather than requiring a
    fresh one per run.
    """
    original_url = settings.database_url
    monkeypatch.setattr(settings, "database_url", _POSTGRES_TEST_DATABASE_URL)

    engine = build_engine(_POSTGRES_TEST_DATABASE_URL)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        engine.dispose()
        pytest.fail(
            f"POSTGRES_TEST_DATABASE_URL was set but the server could not be "
            f"reached: {exc}. Since this variable was explicitly set, this is "
            f"treated as a real infrastructure problem, not silently skipped."
        )

    yield engine

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()
    monkeypatch.setattr(settings, "database_url", original_url)


def _alembic_config():
    return migration_bootstrap._alembic_config()


def test_fresh_postgres_database_migrates_to_the_full_current_schema(postgres_engine):
    """
    The same guarantee tests/test_migrations.py checks against SQLite,
    proven against a real PostgreSQL server: the migration history
    alone builds the exact current schema, no hand-maintained
    SQLite-only approximation.
    """
    alembic_cfg = _alembic_config()

    command.upgrade(alembic_cfg, "head")

    actual_tables = set(inspect(postgres_engine).get_table_names())
    assert actual_tables == _EXPECTED_TABLES | {"alembic_version"}


def test_migrated_postgres_schema_columns_match_current_models(postgres_engine):
    alembic_cfg = _alembic_config()

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(postgres_engine)
    for table in Base.metadata.tables.values():
        actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
        expected_columns = {col.name for col in table.columns}
        assert actual_columns == expected_columns, f"column mismatch on '{table.name}'"


def test_ownership_fields_survive_migration_on_postgres(postgres_engine):
    alembic_cfg = _alembic_config()

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(postgres_engine)
    for table_name in ("documents", "conversations"):
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        assert "owner_type" in columns
        assert "owner_id" in columns


def test_timestamp_columns_are_timezone_aware_on_postgres(postgres_engine):
    """
    PostgreSQL-specific check that has no SQLite equivalent: SQLite has
    no native timestamptz concept, so `DateTime(timezone=True)` (see
    app/db/models.py) can only be verified to actually produce
    `TIMESTAMP WITH TIME ZONE` columns against a real PostgreSQL
    server.
    """
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(postgres_engine)
    documents_columns = {col["name"]: col for col in inspector.get_columns("documents")}
    assert documents_columns["created_at"]["type"].timezone is True


def test_migration_is_reversible_on_postgres(postgres_engine):
    alembic_cfg = _alembic_config()

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    assert set(inspect(postgres_engine).get_table_names()) == {"alembic_version"}

    command.upgrade(alembic_cfg, "head")
    assert set(inspect(postgres_engine).get_table_names()) == _EXPECTED_TABLES | {"alembic_version"}


def test_bootstrap_on_legacy_postgres_database_preserves_existing_data(postgres_engine):
    """
    The PostgreSQL counterpart of
    test_migrations.py::test_bootstrap_on_legacy_database_preserves_existing_data
    -- the single most important safety property in this phase, proven
    against the actual production database target, not just SQLite.
    """
    from sqlalchemy import text

    Base.metadata.create_all(bind=postgres_engine)
    assert "alembic_version" not in inspect(postgres_engine).get_table_names()

    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO guest_sessions (id, created_at, last_seen_at, "
                "document_upload_count, ai_generation_count, chat_message_count) "
                "VALUES ('legacy-guest-token', now(), now(), 1, 2, 3)"
            )
        )

    migration_bootstrap.run_startup_migrations(postgres_engine)

    assert "alembic_version" in inspect(postgres_engine).get_table_names()

    with postgres_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT id, document_upload_count, ai_generation_count, "
                "chat_message_count FROM guest_sessions WHERE id = 'legacy-guest-token'"
            )
        ).one()
    assert row.id == "legacy-guest-token"
    assert row.document_upload_count == 1
    assert row.ai_generation_count == 2
    assert row.chat_message_count == 3


def test_incompatible_legacy_postgres_database_is_not_stamped(postgres_engine):
    """
    The PostgreSQL counterpart of
    test_migrations.py::test_schema_drift_on_incompatible_legacy_database_is_logged_and_not_stamped.
    A legacy database whose schema does not match current models must
    never be falsely stamped at head on PostgreSQL either -- the
    correction this test guards applies to whichever database is
    actually configured, not to a SQLite-only code path.
    """
    from sqlalchemy import text

    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id VARCHAR PRIMARY KEY, "
                "original_filename VARCHAR NOT NULL, "
                "stored_filename VARCHAR NOT NULL, "
                "status VARCHAR NOT NULL"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status) "
                "VALUES ('legacy-doc-1', 'my-notes.pdf', 'stored-my-notes.pdf', 'ready')"
            )
        )

    migration_bootstrap.run_startup_migrations(postgres_engine)

    assert "alembic_version" not in inspect(postgres_engine).get_table_names()
    with postgres_engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, status FROM documents WHERE id = 'legacy-doc-1'")
        ).one()
    assert row.id == "legacy-doc-1"
    assert row.status == "ready"
    actual_columns = {col["name"] for col in inspect(postgres_engine).get_columns("documents")}
    assert "owner_type" not in actual_columns
