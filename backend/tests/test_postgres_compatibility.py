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

from sqlalchemy.orm import Session

from app.api.v1 import routes_documents
from app.core.config import settings
from app.db import migration_bootstrap
from app.db.database import Base, build_engine, is_sqlite_url
from app.db.models import (
    Document,
    GuestSession,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    User,
)
from app.schemas.identity import Identity, IdentityType
from app.services import guest_migration_service, ownership_service

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
    for table_name in ("documents", "conversations", "revision_sessions"):
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
    for table_name in ("documents", "revision_sessions", "revision_questions", "revision_attempts"):
        table_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        assert table_columns["created_at"]["type"].timezone is True


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


def test_revision_document_deletion_durability_on_postgres(postgres_engine):
    """
    Verifies on a live PostgreSQL 16 server that deleting a document:
    - Nullifies source_document_id on RevisionQuestion (foreign key ON DELETE SET NULL).
    - Preserves evidence_snippet and evidence_metadata JSONB on RevisionQuestion.
    - Preserves RevisionSession and RevisionAttempt rows.
    - Preserves un-deleted sister documents and their associations.
    """
    command.upgrade(_alembic_config(), "head")

    with Session(bind=postgres_engine) as session:
        user = User(id="pg-dur-user", email="pgdur@example.com", password_hash="hash")
        session.add(user)
        session.commit()
        ident = Identity(type=IdentityType.USER, id=user.id, user=user)

        doc1 = Document(
            id="pg-doc-1",
            original_filename="pg_biology.pdf",
            stored_filename="stored_pg_biology.pdf",
            status="ready",
            owner_type="user",
            owner_id=user.id,
        )
        doc2 = Document(
            id="pg-doc-2",
            original_filename="pg_chemistry.pdf",
            stored_filename="stored_pg_chemistry.pdf",
            status="ready",
            owner_type="user",
            owner_id=user.id,
        )
        session.add_all([doc1, doc2])
        session.commit()

        rev_session = RevisionSession(
            id="pg-rev-session",
            title="Postgres Durability Session",
            owner_type="user",
            owner_id=user.id,
            status="completed",
            total_questions=2,
            score=1.0,
        )
        session.add(rev_session)
        session.flush()

        assoc1 = RevisionSessionDocument(session_id=rev_session.id, document_id=doc1.id)
        assoc2 = RevisionSessionDocument(session_id=rev_session.id, document_id=doc2.id)
        session.add_all([assoc1, assoc2])

        q1 = RevisionQuestion(
            id="pg-q-1",
            session_id=rev_session.id,
            position=0,
            question_type="multiple_choice",
            question_text="Q1 text",
            correct_answer="A1",
            source_document_id=doc1.id,
            evidence_snippet="Evidence from doc 1 on PostgreSQL.",
            evidence_metadata={"page": 2, "chapter": "Bio"},
        )
        q2 = RevisionQuestion(
            id="pg-q-2",
            session_id=rev_session.id,
            position=1,
            question_type="multiple_choice",
            question_text="Q2 text",
            correct_answer="A2",
            source_document_id=doc2.id,
            evidence_snippet="Evidence from doc 2 on PostgreSQL.",
            evidence_metadata={"page": 5, "chapter": "Chem"},
        )
        session.add_all([q1, q2])
        session.flush()

        att1 = RevisionAttempt(
            id="pg-att-1",
            question_id=q1.id,
            session_id=rev_session.id,
            attempt_number=1,
            submitted_answer="A1",
            is_correct=True,
            score=1.0,
        )
        att2 = RevisionAttempt(
            id="pg-att-2",
            question_id=q2.id,
            session_id=rev_session.id,
            attempt_number=1,
            submitted_answer="A2",
            is_correct=True,
            score=1.0,
        )
        session.add_all([att1, att2])
        session.commit()

        # Delete doc1 via application logic on live PostgreSQL
        routes_documents.delete_document(document_id=doc1.id, db=session, identity=ident)

        # 1. doc1 is removed, doc2 survives
        assert session.query(Document).filter(Document.id == doc1.id).first() is None
        assert session.query(Document).filter(Document.id == doc2.id).first() is not None

        # 2. RevisionSession survives
        persisted_session = session.query(RevisionSession).filter(RevisionSession.id == "pg-rev-session").first()
        assert persisted_session is not None
        assert persisted_session.score == 1.0

        # 3. Association for doc1 is removed; doc2 association survives
        assert (
            session.query(RevisionSessionDocument)
            .filter(RevisionSessionDocument.session_id == "pg-rev-session", RevisionSessionDocument.document_id == doc1.id)
            .first()
        ) is None
        assert (
            session.query(RevisionSessionDocument)
            .filter(RevisionSessionDocument.session_id == "pg-rev-session", RevisionSessionDocument.document_id == doc2.id)
            .first()
        ) is not None

        # 4. Q1 source_document_id is NULL, evidence snippet and JSONB metadata are preserved
        persisted_q1 = session.query(RevisionQuestion).filter(RevisionQuestion.id == "pg-q-1").first()
        assert persisted_q1 is not None
        assert persisted_q1.source_document_id is None
        assert persisted_q1.evidence_snippet == "Evidence from doc 1 on PostgreSQL."
        assert persisted_q1.evidence_metadata == {"page": 2, "chapter": "Bio"}

        # 5. Q2 retains source_document_id
        persisted_q2 = session.query(RevisionQuestion).filter(RevisionQuestion.id == "pg-q-2").first()
        assert persisted_q2 is not None
        assert persisted_q2.source_document_id == doc2.id

        # 6. Both attempts survive
        assert session.query(RevisionAttempt).filter(RevisionAttempt.id == "pg-att-1").first() is not None
        assert session.query(RevisionAttempt).filter(RevisionAttempt.id == "pg-att-2").first() is not None


def test_revision_guest_to_account_migration_on_postgres(postgres_engine):
    """
    Verifies on a live PostgreSQL 16 server that guest_migration_service transfers
    RevisionSession ownership from a guest session to a registered user.
    """
    command.upgrade(_alembic_config(), "head")

    with Session(bind=postgres_engine) as session:
        guest = GuestSession(
            id="pg-guest-mig-token",
            document_upload_count=1,
            ai_generation_count=0,
            chat_message_count=0,
        )
        session.add(guest)
        session.commit()

        doc = Document(
            id="pg-guest-doc",
            original_filename="pg_guest_notes.pdf",
            stored_filename="stored_pg_guest_notes.pdf",
            status="ready",
            owner_type="guest",
            owner_id=guest.id,
        )
        session.add(doc)

        rev_session = RevisionSession(
            id="pg-guest-session",
            title="Guest PG Flashcards",
            owner_type="guest",
            owner_id=guest.id,
            status="in_progress",
        )
        session.add(rev_session)
        session.flush()

        assoc = RevisionSessionDocument(session_id=rev_session.id, document_id=doc.id)
        q = RevisionQuestion(
            id="pg-guest-q",
            session_id=rev_session.id,
            position=0,
            question_type="flashcard",
            question_text="Front",
            correct_answer="Back",
            source_document_id=doc.id,
            evidence_snippet="Evidence on PG",
        )
        session.add_all([assoc, q])
        session.commit()

        # Register target user
        user = User(id="pg-migrated-user", email="pgmigrated@example.com", password_hash="hash")
        session.add(user)
        session.commit()

        # Execute migration
        result = guest_migration_service.migrate_guest_data_to_user(
            db=session,
            guest_session_id=guest.id,
            user_id=user.id,
        )
        session.commit()

        assert result.documents_migrated == 1
        assert result.revision_sessions_migrated == 1

        # Verify on live PostgreSQL
        migrated_doc = session.query(Document).filter(Document.id == doc.id).one()
        assert migrated_doc.owner_type == "user"
        assert migrated_doc.owner_id == user.id

        migrated_s = session.query(RevisionSession).filter(RevisionSession.id == rev_session.id).one()
        assert migrated_s.owner_type == "user"
        assert migrated_s.owner_id == user.id

        # Verify question and assoc preserved
        assert session.query(RevisionSessionDocument).filter(RevisionSessionDocument.session_id == rev_session.id).count() == 1
        assert session.query(RevisionQuestion).filter(RevisionQuestion.session_id == rev_session.id).count() == 1

        # Verify guest session revoked
        revoked_guest = session.query(GuestSession).filter(GuestSession.id == guest.id).one()
        assert revoked_guest.revoked_at is not None


def test_revision_ownership_isolation_on_postgres(postgres_engine):
    """
    Verifies on a live PostgreSQL 16 server that ownership_service correctly scopes
    and isolates RevisionSession queries between distinct users and guests.
    """
    command.upgrade(_alembic_config(), "head")

    with Session(bind=postgres_engine) as session:
        user1 = User(id="pg-user-1", email="pg1@example.com", password_hash="hash")
        user2 = User(id="pg-user-2", email="pg2@example.com", password_hash="hash")
        guest1 = GuestSession(id="pg-guest-1", document_upload_count=0, ai_generation_count=0, chat_message_count=0)
        session.add_all([user1, user2, guest1])
        session.commit()

        ident1 = Identity(type=IdentityType.USER, id=user1.id, user=user1)
        ident2 = Identity(type=IdentityType.USER, id=user2.id, user=user2)
        ident_g1 = Identity(type=IdentityType.GUEST, id=guest1.id, guest_session=guest1)

        s1 = RevisionSession(id="pg-s-1", title="User 1 Session", owner_type="user", owner_id=user1.id)
        s2 = RevisionSession(id="pg-s-2", title="User 2 Session", owner_type="user", owner_id=user2.id)
        s_g1 = RevisionSession(id="pg-s-g1", title="Guest Session", owner_type="guest", owner_id=guest1.id)
        session.add_all([s1, s2, s_g1])
        session.commit()

        # scope_to_owner checks on PostgreSQL
        scoped_user1 = ownership_service.scope_to_owner(session.query(RevisionSession), RevisionSession, ident1).all()
        assert [s.id for s in scoped_user1] == ["pg-s-1"]

        scoped_user2 = ownership_service.scope_to_owner(session.query(RevisionSession), RevisionSession, ident2).all()
        assert [s.id for s in scoped_user2] == ["pg-s-2"]

        scoped_guest1 = ownership_service.scope_to_owner(session.query(RevisionSession), RevisionSession, ident_g1).all()
        assert [s.id for s in scoped_guest1] == ["pg-s-g1"]

        # is_owned_by checks on PostgreSQL
        assert ownership_service.is_owned_by(s1, ident1) is True
        assert ownership_service.is_owned_by(s1, ident2) is False
        assert ownership_service.is_owned_by(s1, ident_g1) is False
        assert ownership_service.is_owned_by(s2, ident1) is False
