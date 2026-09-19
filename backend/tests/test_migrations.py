"""
V3 Milestone 2 Phase 1: database migration framework and startup
bootstrap.

Every other test module in this suite exercises the app through
`TestClient(app)`, which already goes through the real startup path
(see conftest.py: a fresh temp SQLite file is created per test
session, `DATABASE_URL` is pointed at it, and the first `from
app.main import app` anywhere triggers
`migration_bootstrap.run_startup_migrations`) -- so the full backend
suite passing at all is itself a first-order integration test of "an
empty database migrates to a working schema." This file adds the
narrower, more direct checks the migration system itself needs that
the rest of the suite has no reason to cover:

- the migration history can build the schema from nothing, and that
  schema actually matches what the current models define (not just
  "some tables exist")
- the migration history is reversible (a real downgrade path exists,
  not just an upgrade)
- the startup bootstrap's cases (empty / already Alembic-managed /
  legacy-and-matches-current-schema / legacy-and-incompatible -- see
  migration_bootstrap.py's own docstring) each do the right thing,
  especially that a legacy database's existing data is never touched
  and that an incompatible legacy database is never falsely stamped
  as already having the current schema
- schema drift on an incompatible legacy database is surfaced as a
  clear log message and leaves that database unmanaged, rather than
  being silently stamped over or auto-corrected

These tests build their own throwaway SQLite databases (via `tmp_path`)
rather than reusing the shared app engine conftest.py sets up, since
they need to exercise specific before/after database states (empty,
pre-existing-tables-with-data, already-stamped) that the shared app
database won't naturally be in.
"""

import logging

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db import migration_bootstrap
from app.db.database import Base, build_engine

# Every table the current models define. Used throughout to assert
# "the full current schema," not just an arbitrary subset of it.
_EXPECTED_TABLES = set(Base.metadata.tables.keys())


def _alembic_config_for(database_url: str) -> Config:
    """
    An Alembic Config for a specific URL, for tests that need to run
    migrations against a database other than the one the shared `app`
    engine (see conftest.py) is currently pointed at.

    alembic/env.py reads `app.core.config.settings.database_url` at
    run time (see that file's own docstring for why), so redirecting
    a migration run at a different database means updating that
    setting for the duration of the call -- exactly what
    `migration_bootstrap.run_startup_migrations` relies on in
    production too, since it's always called with the engine built
    from that same setting (see app/main.py).
    """
    return migration_bootstrap._alembic_config()


@pytest.fixture()
def temp_database_url(tmp_path, monkeypatch):
    """
    Points `settings.database_url` (and therefore alembic/env.py) at a
    brand-new, empty SQLite file for the duration of one test, and
    restores the original value afterward so later tests (and the
    shared `app` engine other test modules rely on) are unaffected.
    """
    db_path = tmp_path / "migration_test.db"
    url = f"sqlite:///{db_path}"
    original_url = settings.database_url
    monkeypatch.setattr(settings, "database_url", url)
    yield url
    monkeypatch.setattr(settings, "database_url", original_url)


def test_migration_history_has_exactly_one_head():
    """
    A deterministic, reviewable migration history (this phase's
    requirement 9) means there's never an ambiguity about what "head"
    means -- exactly one head revision, not a branch.
    """
    alembic_cfg = migration_bootstrap._alembic_config()
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = script_dir.get_heads()
    assert len(heads) == 1


def test_fresh_database_migrates_to_the_full_current_schema(temp_database_url):
    """
    The core migration-framework guarantee: `alembic upgrade head`
    against nothing builds the exact same set of tables the
    application's models define -- not a hand-maintained approximation
    of them.
    """
    engine = build_engine(temp_database_url)
    alembic_cfg = _alembic_config_for(temp_database_url)

    command.upgrade(alembic_cfg, "head")

    actual_tables = set(inspect(engine).get_table_names())
    assert actual_tables == _EXPECTED_TABLES | {"alembic_version"}
    engine.dispose()


def test_migrated_schema_columns_match_current_models(temp_database_url):
    """
    Table *names* matching isn't sufficient -- checks that every
    column each model defines actually exists on the migrated table,
    catching a migration that creates the right tables with the wrong
    (or missing) columns.
    """
    engine = build_engine(temp_database_url)
    alembic_cfg = _alembic_config_for(temp_database_url)

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        actual_columns = {col["name"] for col in inspector.get_columns(table.name)}
        expected_columns = {col.name for col in table.columns}
        assert actual_columns == expected_columns, f"column mismatch on '{table.name}'"
    engine.dispose()


def test_ownership_fields_survive_migration(temp_database_url):
    """
    This phase's requirement 4: the V3 M1 ownership model
    (Document/Conversation owner_type + owner_id) must remain intact.
    Checked directly against the migrated schema, not just against
    models.py, so a migration that silently dropped these columns
    would be caught here.
    """
    engine = build_engine(temp_database_url)
    alembic_cfg = _alembic_config_for(temp_database_url)

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    for table_name in ("documents", "conversations", "revision_sessions"):
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        assert "owner_type" in columns
        assert "owner_id" in columns
    engine.dispose()


def test_migration_is_reversible(temp_database_url):
    """
    Requirement 9 (migration correctness): a real, working downgrade
    path exists -- this isn't a one-way "create_all with extra steps."
    Downgrading to base must remove every table this migration added,
    and upgrading back to head must reproduce the identical schema.
    """
    engine = build_engine(temp_database_url)
    alembic_cfg = _alembic_config_for(temp_database_url)

    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    # Alembic keeps its own bookkeeping table (now recording "no
    # revision applied") rather than dropping it on a downgrade to
    # base -- every application table this migration created must be
    # gone, but that one is Alembic's own, not a model's.
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    command.upgrade(alembic_cfg, "head")
    assert set(inspect(engine).get_table_names()) == _EXPECTED_TABLES | {"alembic_version"}
    engine.dispose()


def test_bootstrap_on_empty_database_runs_migrations(temp_database_url):
    """
    migration_bootstrap.run_startup_migrations's EMPTY-database case:
    a brand-new database is built via a real `upgrade head`, exactly
    like tests/conftest.py already relies on implicitly for every
    other test module in this suite.
    """
    engine = build_engine(temp_database_url)

    migration_bootstrap.run_startup_migrations(engine)

    actual_tables = set(inspect(engine).get_table_names())
    assert actual_tables == _EXPECTED_TABLES | {"alembic_version"}
    engine.dispose()


def test_bootstrap_on_legacy_database_preserves_existing_data(temp_database_url):
    """
    The single most important safety property in this phase
    (requirements 6 and 9): a pre-Alembic database -- tables created
    directly by the old `Base.metadata.create_all()` bootstrap, with
    real rows already in them -- must be adopted (stamped at head)
    WITHOUT any DDL running against it, and without touching a single
    existing row.
    """
    engine = build_engine(temp_database_url)

    # Simulate the OLD bootstrap: tables created directly, no Alembic
    # involved at all yet.
    Base.metadata.create_all(bind=engine)
    assert "alembic_version" not in inspect(engine).get_table_names()

    # Simulate real pre-existing user data.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO guest_sessions (id, created_at, last_seen_at, "
                "document_upload_count, ai_generation_count, chat_message_count) "
                "VALUES ('legacy-guest-token', '2026-01-01 00:00:00', "
                "'2026-01-01 00:00:00', 1, 2, 3)"
            )
        )

    migration_bootstrap.run_startup_migrations(engine)

    # Adopted: now tracked by Alembic...
    assert "alembic_version" in inspect(engine).get_table_names()

    # ...but the pre-existing row is completely untouched.
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, document_upload_count, ai_generation_count, chat_message_count "
                 "FROM guest_sessions WHERE id = 'legacy-guest-token'")
        ).one()
    assert row.id == "legacy-guest-token"
    assert row.document_upload_count == 1
    assert row.ai_generation_count == 2
    assert row.chat_message_count == 3
    engine.dispose()


def test_bootstrap_on_already_managed_database_is_a_no_op_when_up_to_date(temp_database_url):
    """
    migration_bootstrap.run_startup_migrations's MANAGED-database case:
    calling it again on a database already at head (the normal case on
    every server restart after the first) must not error and must not
    change anything.
    """
    engine = build_engine(temp_database_url)

    migration_bootstrap.run_startup_migrations(engine)
    tables_after_first_run = set(inspect(engine).get_table_names())

    migration_bootstrap.run_startup_migrations(engine)
    tables_after_second_run = set(inspect(engine).get_table_names())

    assert tables_after_first_run == tables_after_second_run
    engine.dispose()


def test_schema_drift_on_incompatible_legacy_database_is_logged_and_not_stamped(temp_database_url, caplog):
    """
    The behavior this correction targets directly: a legacy database
    whose schema does NOT match current models (e.g. it predates V3
    Milestone 1's ownership columns and identity tables entirely) must
    never be stamped at head -- doing so would be a false claim that
    it already has the current schema, which Phase 2's eventual
    SQLite -> PostgreSQL migration (and any other future check) would
    then wrongly trust. It must instead be left unmanaged, with the
    drift clearly reported, and its existing data must be completely
    untouched.
    """
    engine = build_engine(temp_database_url)

    # A deliberately incomplete, genuinely-legacy schema: only
    # 'documents', missing the ownership columns V3 M1 added and
    # missing the guest/user identity tables entirely -- i.e. exactly
    # the kind of pre-V3-M1 SQLite database this correction is about.
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE documents ("
                "id VARCHAR PRIMARY KEY, "
                "original_filename VARCHAR NOT NULL, "
                "stored_filename VARCHAR NOT NULL, "
                "extracted_text TEXT, "
                "status VARCHAR NOT NULL, "
                "created_at DATETIME, "
                "last_opened_at DATETIME, "
                "file_size_bytes INTEGER, "
                "page_count INTEGER"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status) "
                "VALUES ('legacy-doc-1', 'my-notes.pdf', 'stored-my-notes.pdf', 'ready')"
            )
        )

    with caplog.at_level(logging.WARNING, logger="app.db.migration_bootstrap"):
        migration_bootstrap.run_startup_migrations(engine)

    # Not falsely claimed as current: never stamped.
    assert "alembic_version" not in inspect(engine).get_table_names()

    # Clearly reported, not silently ignored.
    assert "documents" in caplog.text
    assert "owner_type" in caplog.text or "owner_id" in caplog.text

    # Existing data completely untouched -- not migrated, not deleted,
    # not altered. The actual SQLite -> PostgreSQL data migration is
    # Phase 2's job, not this correction's.
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, original_filename, status FROM documents WHERE id = 'legacy-doc-1'")
        ).one()
    assert row.id == "legacy-doc-1"
    assert row.original_filename == "my-notes.pdf"
    assert row.status == "ready"

    # No ownership-column migration was invented for this database:
    # the column is still genuinely absent, exactly as requested --
    # reconciling it is left to Phase 2, not patched around here.
    actual_columns = {col["name"] for col in inspect(engine).get_columns("documents")}
    assert "owner_type" not in actual_columns
    assert "owner_id" not in actual_columns
    engine.dispose()


def test_incompatible_legacy_database_still_gets_genuinely_new_tables_created(temp_database_url):
    """
    An incompatible legacy database isn't stamped or migrated, but it
    must still behave exactly as this project's startup always has for
    a table that's new since that database was created: create_all is
    additive-only, so a table that didn't exist before (e.g.
    guest_sessions, added well after 'documents' first existed) is
    still created -- this is what keeps V2.4/V3 M1 behavior intact for
    such a database rather than regressing it, without ever touching
    an existing table's columns or data.
    """
    engine = build_engine(temp_database_url)

    with engine.begin() as connection:
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

    migration_bootstrap.run_startup_migrations(engine)

    tables_after = set(inspect(engine).get_table_names())
    assert "alembic_version" not in tables_after
    assert "guest_sessions" in tables_after  # additive: newly created
    # the pre-existing table was not altered to add the missing column
    documents_columns = {col["name"] for col in inspect(engine).get_columns("documents")}
    assert "owner_type" not in documents_columns
    engine.dispose()


def test_repeated_startups_against_incompatible_legacy_database_stay_stable(temp_database_url):
    """
    An incompatible legacy database is deliberately left unmanaged
    (requirement: do not falsely claim it has the current schema), so
    this same check runs again on every future startup rather than
    being resolved after the first one. That must be safe to do
    repeatedly -- no duplicate-table errors, no change in outcome, no
    accidental stamping on a later run just because it's not the
    first.
    """
    engine = build_engine(temp_database_url)

    with engine.begin() as connection:
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
                "VALUES ('legacy-doc-2', 'a.pdf', 'stored-a.pdf', 'ready')"
            )
        )

    migration_bootstrap.run_startup_migrations(engine)
    migration_bootstrap.run_startup_migrations(engine)
    migration_bootstrap.run_startup_migrations(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id FROM documents WHERE id = 'legacy-doc-2'")
        ).one()
    assert row.id == "legacy-doc-2"
    engine.dispose()
