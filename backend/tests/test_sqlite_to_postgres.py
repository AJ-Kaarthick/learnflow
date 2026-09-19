"""
V3 Milestone 2 Phase 2: SQLite -> PostgreSQL Data Migration & Schema Reconciliation Tests.

Verifies the complete migration suite:
1. Legacy V2.4 schema detection and migration (documents & conversations receive target user ownership).
2. Target user resolution (--target-user-id, --target-user-email, missing, invalid, conflicting).
3. Modern V3 SQLite migration (preserves existing users, guest sessions, and ownership tags).
4. Type normalization (timestamps to UTC TIMESTAMPTZ, booleans, JSON objects, embeddings).
5. Physical file storage validation, copy to target storage, and missing binary detection.
6. Transactional atomicity and rollback on failure (leaves target and source clean).
7. Idempotency and deterministic conflict detection on rerun.
8. Dry-run simulation (no writes persisted to target DB or storage).
9. Real PostgreSQL integration test when POSTGRES_TEST_DATABASE_URL is set.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db import migration_bootstrap
from app.db.cli import run_cli
from app.db.database import Base, build_engine
from app.db.models import (
    Conversation,
    ConversationDocument,
    Document,
    DocumentChunk,
    Flashcard,
    GuestSession,
    Message,
    MindMap,
    QuizQuestion,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
    RevisionSessionDocument,
    Summary,
    User,
    UserSession,
)
from app.db.sqlite_to_postgres import (
    MigrationConflictError,
    MigrationError,
    PhysicalFileMissingError,
    ReferentialIntegrityError,
    SourceSchemaType,
    TargetSchemaNotReadyError,
    TargetUserConflictError,
    TargetUserNotFoundError,
    TargetUserRequiredError,
    UnsupportedSchemaError,
    inspect_source_database,
    migrate_sqlite_to_postgres,
    normalize_bool,
    normalize_datetime,
    normalize_embedding,
    normalize_json,
    resolve_target_user,
    validate_target_database,
)

# ---------------------------------------------------------------------------
# Fixtures and Helpers
# ---------------------------------------------------------------------------


def _setup_target_database(db_url: str) -> None:
    """Migrates a database to Alembic head so it has the full current V3 schema."""
    original_url = settings.database_url
    settings.database_url = db_url
    try:
        alembic_cfg = migration_bootstrap._alembic_config()
        command.upgrade(alembic_cfg, "head")
    finally:
        settings.database_url = original_url


@pytest.fixture
def target_db(tmp_path, monkeypatch):
    """Creates a fresh Alembic-managed target database."""
    target_path = tmp_path / "target_v3.db"
    target_url = f"sqlite:///{target_path}"
    _setup_target_database(target_url)

    # Seed a target user for legacy ownership assignment
    engine = build_engine(target_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('target-user-uuid-1', 'student@example.com', 'hashed_pw_123', '2026-01-01 10:00:00')"
            )
        )
    engine.dispose()
    return target_url


@pytest.fixture
def storage_dirs(tmp_path):
    """Provides isolated source and target storage directories."""
    src_dir = tmp_path / "src_uploads"
    src_dir.mkdir(parents=True, exist_ok=True)
    dst_dir = tmp_path / "dst_uploads"
    dst_dir.mkdir(parents=True, exist_ok=True)
    return src_dir, dst_dir


@pytest.fixture
def legacy_v2_4_db(tmp_path, storage_dirs):
    """
    Creates a representative legacy V2.4 SQLite database with raw DDL
    (no users, no sessions, no owner_type/owner_id on documents or conversations).
    Populates it with valid learning data and corresponding physical files.
    """
    src_storage, _ = storage_dirs
    db_path = tmp_path / "legacy_v2_4.db"
    engine = build_engine(f"sqlite:///{db_path}")

    # Create V2.4 tables
    with engine.begin() as conn:
        conn.execute(
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
        conn.execute(
            text(
                "CREATE TABLE summaries ("
                "id VARCHAR PRIMARY KEY, "
                "document_id VARCHAR NOT NULL UNIQUE, "
                "content TEXT NOT NULL, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE flashcards ("
                "id VARCHAR PRIMARY KEY, "
                "document_id VARCHAR NOT NULL, "
                "question TEXT NOT NULL, "
                "answer TEXT NOT NULL, "
                "position INTEGER NOT NULL, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE quiz_questions ("
                "id VARCHAR PRIMARY KEY, "
                "document_id VARCHAR NOT NULL, "
                "question TEXT NOT NULL, "
                "options JSON NOT NULL, "
                "correct_answer_index INTEGER NOT NULL, "
                "position INTEGER NOT NULL, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE mind_maps ("
                "id VARCHAR PRIMARY KEY, "
                "document_id VARCHAR NOT NULL UNIQUE, "
                "structure JSON NOT NULL, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE document_chunks ("
                "id VARCHAR PRIMARY KEY, "
                "document_id VARCHAR NOT NULL, "
                "chunk_index INTEGER NOT NULL, "
                "content TEXT NOT NULL, "
                "embedding JSON NOT NULL, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE conversations ("
                "id VARCHAR PRIMARY KEY, "
                "title VARCHAR NOT NULL, "
                "title_is_custom BOOLEAN NOT NULL, "
                "created_at DATETIME, "
                "updated_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE messages ("
                "id VARCHAR PRIMARY KEY, "
                "conversation_id VARCHAR NOT NULL, "
                "role VARCHAR NOT NULL, "
                "content TEXT NOT NULL, "
                "position INTEGER NOT NULL, "
                "sources_json JSON, "
                "grounded BOOLEAN, "
                "created_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE conversation_documents ("
                "conversation_id VARCHAR NOT NULL, "
                "document_id VARCHAR NOT NULL, "
                "added_at DATETIME, "
                "PRIMARY KEY (conversation_id, document_id)"
                ")"
            )
        )

        # Seed data
        stored_name_1 = "stored-lecture-1.pdf"
        (src_storage / stored_name_1).write_bytes(b"%PDF-1.4 simulated lecture 1")

        conn.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, extracted_text, status, created_at, file_size_bytes, page_count) "
                "VALUES ('doc-1', 'lecture1.pdf', :sf, 'Lecture 1 content on algorithms', 'ready', '2026-02-01 12:00:00', 1024, 5)"
            ),
            {"sf": stored_name_1},
        )
        conn.execute(
            text(
                "INSERT INTO summaries (id, document_id, content, created_at) "
                "VALUES ('sum-1', 'doc-1', 'Summary of algorithms lecture', '2026-02-01 12:05:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO flashcards (id, document_id, question, answer, position, created_at) "
                "VALUES ('fc-1', 'doc-1', 'What is Big O?', 'Upper bound of runtime', 1, '2026-02-01 12:06:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO quiz_questions (id, document_id, question, options, correct_answer_index, position, created_at) "
                "VALUES ('qq-1', 'doc-1', 'Which is fastest?', '[\"O(1)\", \"O(n)\", \"O(n^2)\"]', 0, 1, '2026-02-01 12:07:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO mind_maps (id, document_id, structure, created_at) "
                "VALUES ('mm-1', 'doc-1', '{\"title\": \"Algorithms\", \"children\": []}', '2026-02-01 12:08:00')"
            )
        )
        fake_embedding = [0.1] * 128
        conn.execute(
            text(
                "INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding, created_at) "
                "VALUES ('chunk-1', 'doc-1', 0, 'Algorithms chunk 0', :emb, '2026-02-01 12:09:00')"
            ),
            {"emb": json.dumps(fake_embedding)},
        )
        conn.execute(
            text(
                "INSERT INTO conversations (id, title, title_is_custom, created_at, updated_at) "
                "VALUES ('convo-1', 'Algorithms Discussion', 1, '2026-02-01 13:00:00', '2026-02-01 13:10:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, role, content, position, sources_json, grounded, created_at) "
                "VALUES ('msg-1', 'convo-1', 'user', 'Explain Big O', 1, NULL, NULL, '2026-02-01 13:00:10')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO messages (id, conversation_id, role, content, position, sources_json, grounded, created_at) "
                "VALUES ('msg-2', 'convo-1', 'assistant', 'Big O represents upper bound', 2, :sources, 1, '2026-02-01 13:00:20')"
            ),
            {"sources": json.dumps([{"chunk_id": "chunk-1", "score": 0.95}])},
        )
        conn.execute(
            text(
                "INSERT INTO conversation_documents (conversation_id, document_id, added_at) "
                "VALUES ('convo-1', 'doc-1', '2026-02-01 13:00:00')"
            )
        )

    engine.dispose()
    return db_path


# ---------------------------------------------------------------------------
# Tests: A. Legacy V2.4 Migration & Ownership
# ---------------------------------------------------------------------------


def test_legacy_v2_4_schema_detection(legacy_v2_4_db):
    engine = build_engine(f"sqlite:///{legacy_v2_4_db}")
    schema_type, counts = inspect_source_database(engine)
    engine.dispose()
    assert schema_type == SourceSchemaType.LEGACY_V2_4
    assert counts["documents"] == 1
    assert counts["conversations"] == 1


def test_legacy_v2_4_migration_without_target_identity_fails_clearly(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs
    with pytest.raises(TargetUserRequiredError) as excinfo:
        migrate_sqlite_to_postgres(
            sqlite_path=legacy_v2_4_db,
            postgres_url=target_db,
            target_user_id=None,
            target_user_email=None,
            source_storage_dir=src_storage,
            target_storage_dir=dst_storage,
        )
    assert "Legacy V2.4 database contains application data" in str(excinfo.value)
    assert "--target-user-id" in str(excinfo.value)


def test_legacy_v2_4_migration_with_target_user_succeeds(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs
    summary = migrate_sqlite_to_postgres(
        sqlite_path=legacy_v2_4_db,
        postgres_url=target_db,
        target_user_email="student@example.com",
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )

    assert summary.success is True
    assert summary.source_type == SourceSchemaType.LEGACY_V2_4
    assert summary.target_user_id == "target-user-uuid-1"
    assert summary.records_migrated["documents"] == 1
    assert summary.records_migrated["conversations"] == 1
    assert summary.records_migrated["summaries"] == 1
    assert summary.records_migrated["flashcards"] == 1
    assert summary.records_migrated["quiz_questions"] == 1
    assert summary.records_migrated["mind_maps"] == 1
    assert summary.records_migrated["document_chunks"] == 1
    assert summary.records_migrated["messages"] == 2
    assert summary.records_migrated["conversation_documents"] == 1

    # Verify ownership in target DB
    target_engine = build_engine(target_db)
    with target_engine.connect() as conn:
        doc = conn.execute(text("SELECT id, owner_type, owner_id FROM documents WHERE id = 'doc-1'")).mappings().one()
        assert doc["owner_type"] == "user"
        assert doc["owner_id"] == "target-user-uuid-1"

        convo = conn.execute(text("SELECT id, owner_type, owner_id FROM conversations WHERE id = 'convo-1'")).mappings().one()
        assert convo["owner_type"] == "user"
        assert convo["owner_id"] == "target-user-uuid-1"

        # Verify child relations
        sum_row = conn.execute(text("SELECT document_id, content FROM summaries WHERE id = 'sum-1'")).mappings().one()
        assert sum_row["document_id"] == "doc-1"

        msg_rows = conn.execute(text("SELECT id, role, position, grounded FROM messages WHERE conversation_id = 'convo-1' ORDER BY position")).mappings().all()
        assert len(msg_rows) == 2
        assert msg_rows[0]["role"] == "user"
        assert msg_rows[1]["role"] == "assistant"
        assert bool(msg_rows[1]["grounded"]) is True

        cd_row = conn.execute(text("SELECT conversation_id, document_id FROM conversation_documents")).mappings().one()
        assert cd_row["conversation_id"] == "convo-1"
        assert cd_row["document_id"] == "doc-1"
    target_engine.dispose()

    # Verify physical file was copied
    assert (dst_storage / "stored-lecture-1.pdf").is_file()


# ---------------------------------------------------------------------------
# Tests: B. Target User Resolution
# ---------------------------------------------------------------------------


def test_target_user_resolution_by_id(target_db):
    engine = build_engine(target_db)
    user = resolve_target_user(engine, target_user_id="target-user-uuid-1")
    engine.dispose()
    assert user is not None
    assert user.id == "target-user-uuid-1"
    assert user.email == "student@example.com"


def test_target_user_resolution_by_email(target_db):
    engine = build_engine(target_db)
    user = resolve_target_user(engine, target_user_email="student@example.com")
    engine.dispose()
    assert user is not None
    assert user.id == "target-user-uuid-1"


def test_target_user_resolution_nonexistent_fails(target_db):
    engine = build_engine(target_db)
    with pytest.raises(TargetUserNotFoundError):
        resolve_target_user(engine, target_user_email="ghost@example.com")
    with pytest.raises(TargetUserNotFoundError):
        resolve_target_user(engine, target_user_id="nonexistent-id")
    engine.dispose()


def test_target_user_resolution_conflicting_id_and_email(target_db):
    engine = build_engine(target_db)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('user-2', 'second@example.com', 'pw', '2026-01-01 00:00:00')"
            )
        )
    with pytest.raises(TargetUserConflictError):
        resolve_target_user(engine, target_user_id="target-user-uuid-1", target_user_email="second@example.com")
    engine.dispose()


# ---------------------------------------------------------------------------
# Tests: C. Modern V3 SQLite Migration
# ---------------------------------------------------------------------------


def test_modern_v3_sqlite_migration(tmp_path, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs
    src_db_path = tmp_path / "modern_v3_source.db"
    src_url = f"sqlite:///{src_db_path}"
    _setup_target_database(src_url)

    # Populate modern V3 data
    src_engine = build_engine(src_url)
    stored_name = "v3-doc.pdf"
    (src_storage / stored_name).write_bytes(b"%PDF-1.4 modern v3 content")

    with src_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('v3-author', 'author@example.com', 'hashed_auth', '2026-03-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO guest_sessions (id, created_at, last_seen_at, document_upload_count, ai_generation_count, chat_message_count) "
                "VALUES ('guest-token-abc', '2026-03-01 01:00:00', '2026-03-01 01:30:00', 1, 1, 2)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status, owner_type, owner_id, created_at) "
                "VALUES ('doc-user', 'user_notes.pdf', :sf, 'ready', 'user', 'v3-author', '2026-03-01 02:00:00')"
            ),
            {"sf": stored_name},
        )
        conn.execute(
            text(
                "INSERT INTO conversations (id, title, title_is_custom, owner_type, owner_id, created_at, updated_at) "
                "VALUES ('convo-guest', 'Guest Chat', 0, 'guest', 'guest-token-abc', '2026-03-01 02:10:00', '2026-03-01 02:20:00')"
            )
        )
    src_engine.dispose()

    # Migrate without specifying a target user (modern V3 already has its own ownership)
    summary = migrate_sqlite_to_postgres(
        sqlite_path=src_db_path,
        postgres_url=target_db,
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )

    assert summary.success is True
    assert summary.source_type == SourceSchemaType.MODERN_V3
    assert summary.records_migrated["users"] == 1
    assert summary.records_migrated["guest_sessions"] == 1
    assert summary.records_migrated["documents"] == 1
    assert summary.records_migrated["conversations"] == 1

    # Verify preserved ownership in target
    target_engine = build_engine(target_db)
    with target_engine.connect() as conn:
        doc = conn.execute(text("SELECT id, owner_type, owner_id FROM documents WHERE id = 'doc-user'")).mappings().one()
        assert doc["owner_type"] == "user"
        assert doc["owner_id"] == "v3-author"

        convo = conn.execute(text("SELECT id, owner_type, owner_id FROM conversations WHERE id = 'convo-guest'")).mappings().one()
        assert convo["owner_type"] == "guest"
        assert convo["owner_id"] == "guest-token-abc"
    target_engine.dispose()


def test_modern_v3_migration_with_revision_data(tmp_path, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs
    src_db_path = tmp_path / "v3_revision_source.db"
    src_url = f"sqlite:///{src_db_path}"
    _setup_target_database(src_url)

    src_engine = build_engine(src_url)
    stored_name_1 = "rev-doc-1.pdf"
    stored_name_2 = "rev-doc-2.pdf"
    (src_storage / stored_name_1).write_bytes(b"%PDF-1.4 Biology Chapter 1")
    (src_storage / stored_name_2).write_bytes(b"%PDF-1.4 Chemistry Chapter 1")

    with src_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('user-rev-owner', 'revowner@example.com', 'hashed_pw', '2026-03-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO guest_sessions (id, created_at, last_seen_at, document_upload_count, ai_generation_count, chat_message_count) "
                "VALUES ('guest-rev-token', '2026-03-01 01:00:00', '2026-03-01 01:30:00', 0, 0, 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status, owner_type, owner_id, created_at) "
                "VALUES ('doc-bio', 'biology.pdf', :sf1, 'ready', 'user', 'user-rev-owner', '2026-03-01 02:00:00'), "
                "       ('doc-chem', 'chemistry.pdf', :sf2, 'ready', 'user', 'user-rev-owner', '2026-03-01 02:05:00')"
            ),
            {"sf1": stored_name_1, "sf2": stored_name_2},
        )
        conn.execute(
            text(
                "INSERT INTO revision_sessions (id, title, owner_type, owner_id, status, config, total_questions, score, created_at) "
                "VALUES ('session-user-1', 'Bio & Chem Review', 'user', 'user-rev-owner', 'completed', '{\"difficulty\": \"medium\"}', 2, 1.0, '2026-03-01 03:00:00'), "
                "       ('session-guest-1', 'Guest Quick Quiz', 'guest', 'guest-rev-token', 'in_progress', NULL, 1, NULL, '2026-03-01 03:10:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_session_documents (session_id, document_id, added_at) "
                "VALUES ('session-user-1', 'doc-bio', '2026-03-01 03:01:00'), "
                "       ('session-user-1', 'doc-chem', '2026-03-01 03:02:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_questions (id, session_id, position, question_type, question_text, options, correct_answer, explanation, source_document_id, evidence_snippet, evidence_metadata, created_at) "
                "VALUES ('q-1', 'session-user-1', 0, 'multiple_choice', 'What is mitosis?', '[\"Cell division\", \"Respiration\"]', 'Cell division', 'Mitosis divides cells.', 'doc-bio', 'Cells divide by mitosis.', '{\"page\": 1}', '2026-03-01 03:05:00'), "
                "       ('q-2', 'session-user-1', 1, 'multiple_choice', 'What is H2O?', '[\"Water\", \"Oxygen\"]', 'Water', 'H2O is water.', NULL, NULL, NULL, '2026-03-01 03:06:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_attempts (id, question_id, session_id, attempt_number, submitted_answer, is_correct, score, feedback, created_at) "
                "VALUES ('att-1', 'q-1', 'session-user-1', 1, 'Respiration', 0, 0.0, 'Incorrect', '2026-03-01 03:07:00'), "
                "       ('att-2', 'q-1', 'session-user-1', 2, 'Cell division', 1, 1.0, 'Correct!', '2026-03-01 03:08:00')"
            )
        )
    src_engine.dispose()

    summary = migrate_sqlite_to_postgres(
        sqlite_path=src_db_path,
        postgres_url=target_db,
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )

    assert summary.success is True
    assert summary.source_type == SourceSchemaType.MODERN_V3
    assert summary.records_migrated["users"] == 1
    assert summary.records_migrated["guest_sessions"] == 1
    assert summary.records_migrated["documents"] == 2
    assert summary.records_migrated["revision_sessions"] == 2
    assert summary.records_migrated["revision_session_documents"] == 2
    assert summary.records_migrated["revision_questions"] == 2
    assert summary.records_migrated["revision_attempts"] == 2

    # Verify target records and relationships
    target_engine = build_engine(target_db)
    with target_engine.connect() as conn:
        # Check sessions & ownership
        s1 = conn.execute(text("SELECT id, title, owner_type, owner_id, status, config, total_questions, score FROM revision_sessions WHERE id = 'session-user-1'")).mappings().one()
        assert s1["owner_type"] == "user"
        assert s1["owner_id"] == "user-rev-owner"
        assert s1["total_questions"] == 2
        cfg = json.loads(s1["config"]) if isinstance(s1["config"], str) else s1["config"]
        assert cfg["difficulty"] == "medium"

        s2 = conn.execute(text("SELECT id, owner_type, owner_id, status FROM revision_sessions WHERE id = 'session-guest-1'")).mappings().one()
        assert s2["owner_type"] == "guest"
        assert s2["owner_id"] == "guest-rev-token"

        # Check document associations
        assocs = conn.execute(text("SELECT session_id, document_id FROM revision_session_documents WHERE session_id = 'session-user-1' ORDER BY document_id")).mappings().all()
        assert len(assocs) == 2
        assert {a["document_id"] for a in assocs} == {"doc-bio", "doc-chem"}

        # Check questions, ordering, evidence snapshot, and nullable source_document_id
        questions = conn.execute(text("SELECT id, session_id, position, question_text, options, correct_answer, source_document_id, evidence_snippet, evidence_metadata FROM revision_questions WHERE session_id = 'session-user-1' ORDER BY position")).mappings().all()
        assert len(questions) == 2
        assert questions[0]["id"] == "q-1"
        assert questions[0]["position"] == 0
        assert questions[0]["source_document_id"] == "doc-bio"
        assert questions[0]["evidence_snippet"] == "Cells divide by mitosis."
        meta0 = json.loads(questions[0]["evidence_metadata"]) if isinstance(questions[0]["evidence_metadata"], str) else questions[0]["evidence_metadata"]
        assert meta0["page"] == 1
        opts0 = json.loads(questions[0]["options"]) if isinstance(questions[0]["options"], str) else questions[0]["options"]
        assert opts0 == ["Cell division", "Respiration"]

        assert questions[1]["id"] == "q-2"
        assert questions[1]["position"] == 1
        assert questions[1]["source_document_id"] is None
        assert questions[1]["evidence_snippet"] is None

        # Check attempts, attempt_number order, score, boolean is_correct
        attempts = conn.execute(text("SELECT id, question_id, attempt_number, submitted_answer, is_correct, score, feedback FROM revision_attempts WHERE question_id = 'q-1' ORDER BY attempt_number")).mappings().all()
        assert len(attempts) == 2
        assert attempts[0]["attempt_number"] == 1
        assert bool(attempts[0]["is_correct"]) is False
        assert attempts[0]["score"] == 0.0
        assert attempts[1]["attempt_number"] == 2
        assert bool(attempts[1]["is_correct"]) is True
        assert attempts[1]["score"] == 1.0

    # Idempotent rerun verification
    rerun_summary = migrate_sqlite_to_postgres(
        sqlite_path=src_db_path,
        postgres_url=target_db,
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )
    assert rerun_summary.success is True
    assert rerun_summary.records_migrated["revision_sessions"] == 0
    assert rerun_summary.records_skipped["revision_sessions"] == 2
    assert rerun_summary.records_migrated["revision_questions"] == 0
    assert rerun_summary.records_skipped["revision_questions"] == 2
    assert rerun_summary.records_migrated["revision_attempts"] == 0
    assert rerun_summary.records_skipped["revision_attempts"] == 2
    assert rerun_summary.records_migrated["revision_session_documents"] == 0
    assert rerun_summary.records_skipped["revision_session_documents"] == 2
    target_engine.dispose()


# ---------------------------------------------------------------------------
# Tests: D. Type Normalization
# ---------------------------------------------------------------------------


def test_type_normalization_utilities():
    # Timestamps
    dt_iso = normalize_datetime("2026-04-15 14:30:00.123456")
    assert dt_iso is not None
    assert dt_iso.tzinfo == timezone.utc
    assert dt_iso.year == 2026
    assert dt_iso.hour == 14

    dt_aware = normalize_datetime(datetime(2026, 4, 15, 14, 30, tzinfo=timezone.utc))
    assert dt_aware.tzinfo == timezone.utc

    # Booleans
    assert normalize_bool(1) is True
    assert normalize_bool(0) is False
    assert normalize_bool("true") is True
    assert normalize_bool("false") is False
    assert normalize_bool(None) is None

    # JSON & Embeddings
    raw_opts = '["OptA", "OptB"]'
    assert normalize_json(raw_opts) == ["OptA", "OptB"]
    raw_emb = "[0.1, 0.2, 0.3]"
    assert normalize_embedding(raw_emb) == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# Tests: E. Physical Files Validation & Handling
# ---------------------------------------------------------------------------


def test_missing_physical_file_aborts_migration(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs
    # Delete the source physical file to trigger error
    (src_storage / "stored-lecture-1.pdf").unlink()

    with pytest.raises(PhysicalFileMissingError) as excinfo:
        migrate_sqlite_to_postgres(
            sqlite_path=legacy_v2_4_db,
            postgres_url=target_db,
            target_user_email="student@example.com",
            source_storage_dir=src_storage,
            target_storage_dir=dst_storage,
        )
    assert "missing from source storage" in str(excinfo.value)
    assert "stored-lecture-1.pdf" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Tests: F. Transaction Rollback on Failure
# ---------------------------------------------------------------------------


def test_transaction_rollback_cleans_up_and_leaves_source_intact(legacy_v2_4_db, target_db, storage_dirs, monkeypatch):
    src_storage, dst_storage = storage_dirs

    # Force an exception midway through table insertion
    from app.db import sqlite_to_postgres

    original_insert = Base.metadata.tables["messages"].insert

    def _exploding_insert(*args, **kwargs):
        raise RuntimeError("Simulated mid-transaction database failure")

    monkeypatch.setattr(Base.metadata.tables["messages"], "insert", _exploding_insert)

    with pytest.raises(MigrationError) as excinfo:
        migrate_sqlite_to_postgres(
            sqlite_path=legacy_v2_4_db,
            postgres_url=target_db,
            target_user_email="student@example.com",
            source_storage_dir=src_storage,
            target_storage_dir=dst_storage,
        )
    assert "Simulated mid-transaction database failure" in str(excinfo.value)

    # Verify target DB has 0 migrated documents or conversations (clean rollback)
    target_engine = build_engine(target_db)
    with target_engine.connect() as conn:
        doc_count = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        assert doc_count == 0
        convo_count = conn.execute(text("SELECT COUNT(*) FROM conversations")).scalar()
        assert convo_count == 0
    target_engine.dispose()

    # Verify newly copied file was removed from target storage
    assert not (dst_storage / "stored-lecture-1.pdf").exists()

    # Verify source file remains untouched
    assert (src_storage / "stored-lecture-1.pdf").is_file()


# ---------------------------------------------------------------------------
# Tests: G. Idempotency & Conflict Handling
# ---------------------------------------------------------------------------


def test_rerunning_migration_is_idempotent(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs

    # First run: migrates data
    summary1 = migrate_sqlite_to_postgres(
        sqlite_path=legacy_v2_4_db,
        postgres_url=target_db,
        target_user_email="student@example.com",
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )
    assert summary1.records_migrated["documents"] == 1
    assert summary1.records_skipped["documents"] == 0

    # Second run: identical data skipped
    summary2 = migrate_sqlite_to_postgres(
        sqlite_path=legacy_v2_4_db,
        postgres_url=target_db,
        target_user_email="student@example.com",
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )
    assert summary2.records_migrated["documents"] == 0
    assert summary2.records_skipped["documents"] == 1
    assert summary2.records_skipped["conversations"] == 1


def test_migration_conflicts_fail_explicitly(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs

    # Seed conflicting document in target with same ID but different filename
    target_engine = build_engine(target_db)
    with target_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status, created_at) "
                "VALUES ('doc-1', 'conflict.pdf', 'different-stored.pdf', 'ready', '2026-01-01 00:00:00')"
            )
        )
    target_engine.dispose()

    with pytest.raises(MigrationConflictError) as excinfo:
        migrate_sqlite_to_postgres(
            sqlite_path=legacy_v2_4_db,
            postgres_url=target_db,
            target_user_email="student@example.com",
            source_storage_dir=src_storage,
            target_storage_dir=dst_storage,
        )
    assert "Document ID 'doc-1' already exists in target with different stored_filename" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Tests: H. Dry Run
# ---------------------------------------------------------------------------


def test_dry_run_does_not_persist_data_or_files(legacy_v2_4_db, target_db, storage_dirs):
    src_storage, dst_storage = storage_dirs

    summary = migrate_sqlite_to_postgres(
        sqlite_path=legacy_v2_4_db,
        postgres_url=target_db,
        target_user_email="student@example.com",
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
        dry_run=True,
    )

    assert summary.dry_run is True
    assert summary.records_migrated["documents"] == 1
    assert summary.files_validated == 1

    # Verify no documents in target
    target_engine = build_engine(target_db)
    with target_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        assert count == 0
    target_engine.dispose()

    # Verify no files copied
    assert not (dst_storage / "stored-lecture-1.pdf").exists()


# ---------------------------------------------------------------------------
# Tests: CLI Interface
# ---------------------------------------------------------------------------


def test_cli_execution(legacy_v2_4_db, target_db, storage_dirs, capsys):
    src_storage, dst_storage = storage_dirs
    exit_code = run_cli([
        "migrate",
        "--sqlite-path", str(legacy_v2_4_db),
        "--postgres-url", target_db,
        "--target-user-email", "student@example.com",
        "--source-storage-dir", str(src_storage),
        "--target-storage-dir", str(dst_storage),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "LearnFlow V3 Database Migration Summary" in captured.out
    assert "Status:             SUCCESS" in captured.out


# ---------------------------------------------------------------------------
# Tests: I. PostgreSQL Integration (Opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.postgres
def test_real_postgres_integration(legacy_v2_4_db, storage_dirs):
    postgres_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL not set; skipping live PostgreSQL test.")

    src_storage, dst_storage = storage_dirs
    _setup_target_database(postgres_url)

    # Seed target user in PostgreSQL
    engine = build_engine(postgres_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('pg-target-user-1', 'pgstudent@example.com', 'hashed_pass', now())"
            )
        )
    engine.dispose()

    summary = migrate_sqlite_to_postgres(
        sqlite_path=legacy_v2_4_db,
        postgres_url=postgres_url,
        target_user_email="pgstudent@example.com",
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )

    assert summary.success is True
    assert summary.records_migrated["documents"] == 1
    assert summary.records_migrated["conversations"] == 1

    # Verify ownership and child data in PostgreSQL
    engine = build_engine(postgres_url)
    with engine.connect() as conn:
        doc = conn.execute(text("SELECT id, owner_type, owner_id FROM documents WHERE id = 'doc-1'")).mappings().one()
        assert doc["owner_type"] == "user"
        assert doc["owner_id"] == "pg-target-user-1"

        convo = conn.execute(text("SELECT id, owner_type, owner_id FROM conversations WHERE id = 'convo-1'")).mappings().one()
        assert convo["owner_type"] == "user"
        assert convo["owner_id"] == "pg-target-user-1"
    engine.dispose()

    # Cleanup target database
    engine = build_engine(postgres_url)
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()


@pytest.mark.postgres
def test_real_postgres_modern_v3_integration(tmp_path, storage_dirs):
    postgres_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL not set; skipping live PostgreSQL test.")

    src_storage, dst_storage = storage_dirs
    src_db_path = tmp_path / "modern_v3_pg_test.db"
    src_url = f"sqlite:///{src_db_path}"
    _setup_target_database(src_url)

    stored_name = "v3-pg-doc.pdf"
    (src_storage / stored_name).write_bytes(b"%PDF-1.4 modern v3 live postgres test")

    src_engine = build_engine(src_url)
    with src_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('v3-pg-author', 'pgauthor@example.com', 'hashed_pass_v3', '2026-03-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO guest_sessions (id, created_at, last_seen_at, document_upload_count, ai_generation_count, chat_message_count) "
                "VALUES ('guest-pg-session', '2026-03-01 01:00:00', '2026-03-01 01:30:00', 1, 0, 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO documents (id, original_filename, stored_filename, status, owner_type, owner_id, created_at) "
                "VALUES ('doc-v3-pg', 'v3_notes.pdf', :sf, 'ready', 'user', 'v3-pg-author', '2026-03-01 02:00:00')"
            ),
            {"sf": stored_name},
        )
        conn.execute(
            text(
                "INSERT INTO conversations (id, title, title_is_custom, owner_type, owner_id, created_at, updated_at) "
                "VALUES ('convo-v3-pg', 'Guest PG Chat', 0, 'guest', 'guest-pg-session', '2026-03-01 02:10:00', '2026-03-01 02:20:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_sessions (id, title, owner_type, owner_id, status, config, total_questions, score, created_at) "
                "VALUES ('session-pg-1', 'PG Live Revision', 'user', 'v3-pg-author', 'completed', '{\"level\": \"advanced\"}', 1, 1.0, '2026-03-01 03:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_session_documents (session_id, document_id, added_at) "
                "VALUES ('session-pg-1', 'doc-v3-pg', '2026-03-01 03:01:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_questions (id, session_id, position, question_type, question_text, options, correct_answer, explanation, source_document_id, evidence_snippet, evidence_metadata, created_at) "
                "VALUES ('q-pg-1', 'session-pg-1', 0, 'multiple_choice', 'Is PG live?', '[\"Yes\", \"No\"]', 'Yes', 'It is live.', 'doc-v3-pg', 'Live PG evidence', '{\"section\": \"intro\"}', '2026-03-01 03:05:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO revision_attempts (id, question_id, session_id, attempt_number, submitted_answer, is_correct, score, feedback, created_at) "
                "VALUES ('att-pg-1', 'q-pg-1', 'session-pg-1', 1, 'Yes', 1, 1.0, 'Correct!', '2026-03-01 03:06:00')"
            )
        )
    src_engine.dispose()

    # Clean and setup target PostgreSQL database
    engine = build_engine(postgres_url)
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()

    _setup_target_database(postgres_url)

    summary = migrate_sqlite_to_postgres(
        sqlite_path=src_db_path,
        postgres_url=postgres_url,
        source_storage_dir=src_storage,
        target_storage_dir=dst_storage,
    )

    assert summary.success is True
    assert summary.source_type == SourceSchemaType.MODERN_V3
    assert summary.records_migrated["users"] == 1
    assert summary.records_migrated["guest_sessions"] == 1
    assert summary.records_migrated["documents"] == 1
    assert summary.records_migrated["conversations"] == 1
    assert summary.records_migrated["revision_sessions"] == 1
    assert summary.records_migrated["revision_session_documents"] == 1
    assert summary.records_migrated["revision_questions"] == 1
    assert summary.records_migrated["revision_attempts"] == 1

    # Verify preserved ownership in live PostgreSQL
    engine = build_engine(postgres_url)
    with engine.connect() as conn:
        user_row = conn.execute(text("SELECT id, email FROM users WHERE id = 'v3-pg-author'")).mappings().one()
        assert user_row["email"] == "pgauthor@example.com"

        guest_row = conn.execute(text("SELECT id, document_upload_count FROM guest_sessions WHERE id = 'guest-pg-session'")).mappings().one()
        assert guest_row["document_upload_count"] == 1

        doc = conn.execute(text("SELECT id, owner_type, owner_id FROM documents WHERE id = 'doc-v3-pg'")).mappings().one()
        assert doc["owner_type"] == "user"
        assert doc["owner_id"] == "v3-pg-author"

        convo = conn.execute(text("SELECT id, owner_type, owner_id FROM conversations WHERE id = 'convo-v3-pg'")).mappings().one()
        assert convo["owner_type"] == "guest"
        assert convo["owner_id"] == "guest-pg-session"

        rev_s = conn.execute(text("SELECT id, owner_type, owner_id, status, config, score FROM revision_sessions WHERE id = 'session-pg-1'")).mappings().one()
        assert rev_s["owner_type"] == "user"
        assert rev_s["owner_id"] == "v3-pg-author"
        assert rev_s["config"]["level"] == "advanced"
        assert rev_s["score"] == 1.0

        rev_doc = conn.execute(text("SELECT session_id, document_id FROM revision_session_documents WHERE session_id = 'session-pg-1'")).mappings().one()
        assert rev_doc["document_id"] == "doc-v3-pg"

        rev_q = conn.execute(text("SELECT id, source_document_id, evidence_snippet, evidence_metadata, options FROM revision_questions WHERE id = 'q-pg-1'")).mappings().one()
        assert rev_q["source_document_id"] == "doc-v3-pg"
        assert rev_q["evidence_snippet"] == "Live PG evidence"
        assert rev_q["evidence_metadata"]["section"] == "intro"
        assert rev_q["options"] == ["Yes", "No"]

        rev_att = conn.execute(text("SELECT id, is_correct, score, feedback FROM revision_attempts WHERE id = 'att-pg-1'")).mappings().one()
        assert rev_att["is_correct"] is True
        assert rev_att["score"] == 1.0
    engine.dispose()

    # Verify physical file in target storage
    assert (dst_storage / stored_name).is_file()

    # Cleanup PostgreSQL
    engine = build_engine(postgres_url)
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()


@pytest.mark.postgres
def test_real_postgres_unprepared_target_fails_clearly(legacy_v2_4_db, storage_dirs):
    postgres_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if not postgres_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL not set; skipping live PostgreSQL test.")

    src_storage, dst_storage = storage_dirs

    # Ensure target PostgreSQL is empty (no alembic_version table)
    engine = build_engine(postgres_url)
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    engine.dispose()

    with pytest.raises(TargetSchemaNotReadyError) as excinfo:
        migrate_sqlite_to_postgres(
            sqlite_path=legacy_v2_4_db,
            postgres_url=postgres_url,
            target_user_email="any@example.com",
            source_storage_dir=src_storage,
            target_storage_dir=dst_storage,
        )

    assert "alembic_version" in str(excinfo.value)
    assert "alembic upgrade head" in str(excinfo.value)

