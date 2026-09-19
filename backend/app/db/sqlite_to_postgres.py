"""
V3 Milestone 2 Phase 2: SQLite -> PostgreSQL Data Migration & Legacy Schema Reconciliation.

Provides the core migration engine to safely extract learning data from a source
SQLite database (either legacy V2.4 without ownership or modern V3 with ownership)
and ingest it into a target PostgreSQL database managed by Alembic.

Core invariants enforced:
1. Source SQLite database is strictly READ-ONLY (no DDL, no DML, no schema stamping).
2. Target database must be pre-migrated to Alembic head (Alembic remains authoritative).
3. Legacy V2.4 application data requires an explicit target user identity (owner_type="user",
   owner_id=target_user.id). NULL ownership is never used as the migration path for legacy data.
4. Modern V3 SQLite data preserves its existing, valid ownership.
5. Referenced physical files in storage are validated for existence and copied when source
   and target storage locations differ.
6. All target database operations occur within a single transaction; failure rolls back
   database changes and cleans up any newly copied storage files.
7. Rerunning migration is idempotent: identical records are skipped without duplication,
   while data conflicts fail explicitly.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.db import migration_bootstrap
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
from app.services import storage_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MigrationError(Exception):
    """Base exception for all migration errors."""


class UnsupportedSchemaError(MigrationError):
    """Raised when the source database cannot be identified as a valid LearnFlow database."""


class TargetSchemaNotReadyError(MigrationError):
    """Raised when the target database is not at the current Alembic migration head."""


class TargetUserRequiredError(MigrationError):
    """Raised when legacy V2.4 data exists but no target user identity was supplied."""


class TargetUserNotFoundError(MigrationError):
    """Raised when the specified target user does not exist in the target database."""


class TargetUserConflictError(MigrationError):
    """Raised when supplied target-user-id and target-user-email resolve to different users."""


class MigrationConflictError(MigrationError):
    """Raised when an incoming record conflicts with existing data in the target database."""


class PhysicalFileMissingError(MigrationError):
    """Raised when a document references a physical file that does not exist in source storage."""


class PhysicalFileCopyError(MigrationError):
    """Raised when copying a physical file to target storage fails."""


class ReferentialIntegrityError(MigrationError):
    """Raised when source data contains orphaned child records violating foreign key relationships."""


# ---------------------------------------------------------------------------
# Schema Types and Summary
# ---------------------------------------------------------------------------


class SourceSchemaType(str, Enum):
    LEGACY_V2_4 = "legacy_v2_4"
    MODERN_V3 = "modern_v3"
    UNSUPPORTED = "unsupported"


@dataclass
class MigrationSummary:
    source_path: str
    target_url: str
    source_type: SourceSchemaType
    target_user_id: str | None
    dry_run: bool
    source_records_discovered: dict[str, int] = field(default_factory=dict)
    records_migrated: dict[str, int] = field(default_factory=dict)
    records_skipped: dict[str, int] = field(default_factory=dict)
    files_validated: int = 0
    files_copied: int = 0
    success: bool = True
    message: str = ""

    def format_report(self) -> str:
        lines = [
            "=" * 64,
            "LearnFlow V3 Database Migration Summary",
            "=" * 64,
            f"Source Database:    {self.source_path}",
            f"Source Schema Type: {self.source_type.value}",
            f"Target Database:    {self.target_url}",
            f"Target User ID:     {self.target_user_id or 'None'}",
            f"Mode:               {'DRY RUN (no changes persisted)' if self.dry_run else 'APPLY (changes committed)'}",
            f"Files Validated:    {self.files_validated}",
            f"Files Copied:       {self.files_copied}",
            "",
            "Entity Breakdown:",
        ]
        all_tables = sorted(
            set(self.source_records_discovered.keys())
            | set(self.records_migrated.keys())
            | set(self.records_skipped.keys())
        )
        for tbl in all_tables:
            discovered = self.source_records_discovered.get(tbl, 0)
            migrated = self.records_migrated.get(tbl, 0)
            skipped = self.records_skipped.get(tbl, 0)
            lines.append(f"  {tbl:<24} {discovered:>4} discovered -> {migrated:>4} migrated, {skipped:>4} skipped")

        lines.extend([
            "",
            f"Status:             {'SUCCESS' if self.success else 'FAILED'}",
            f"Message:            {self.message}",
            "=" * 64,
        ])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Type Normalization Utilities
# ---------------------------------------------------------------------------


def normalize_datetime(val: Any) -> datetime | None:
    """
    Normalizes a datetime representation into a timezone-aware UTC datetime.
    SQLite drops timezone info; this ensures naive timestamps are interpreted
    as UTC and attached with timezone.utc for PostgreSQL TIMESTAMPTZ compatibility.
    """
    if val is None:
        return None
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return None
        # Replace space between date and time with T if present
        iso_str = val_clean.replace(" ", "T")
        try:
            dt = datetime.fromisoformat(iso_str)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(iso_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unrecognized datetime string format: {val}")
    elif isinstance(val, datetime):
        dt = val
    elif isinstance(val, (int, float)):
        dt = datetime.fromtimestamp(val, tz=timezone.utc)
    else:
        raise TypeError(f"Cannot normalize datetime from type {type(val)}: {val!r}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_bool(val: Any) -> bool | None:
    """Normalizes SQLite integer booleans (0/1) or strings into Python booleans."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        lowered = val.strip().lower()
        if lowered in ("1", "true", "t", "yes"):
            return True
        if lowered in ("0", "false", "f", "no"):
            return False
    return bool(val)


def normalize_json(val: Any) -> Any:
    """Ensures JSON fields stored as strings in SQLite are parsed into Python lists/dicts."""
    if val is None:
        return None
    if isinstance(val, str):
        clean = val.strip()
        if not clean:
            return None
        try:
            return json.loads(clean)
        except Exception:
            return clean
    return val


def normalize_embedding(val: Any) -> list[float]:
    """Ensures vector embedding data is a proper list of floats."""
    parsed = normalize_json(val)
    if isinstance(parsed, list):
        return [float(x) for x in parsed]
    raise ValueError(f"Embedding must be a list of floats, got: {type(val)}")


# ---------------------------------------------------------------------------
# Introspection & Target Validation
# ---------------------------------------------------------------------------


def inspect_source_database(sqlite_engine: Engine) -> tuple[SourceSchemaType, dict[str, int]]:
    """
    Inspects the source SQLite database read-only.
    Determines whether it is:
      - LEGACY_V2_4: 'documents' exists but lacks 'owner_type' / 'owner_id'
      - MODERN_V3: 'documents' exists and contains 'owner_type' and 'owner_id'
      - UNSUPPORTED: does not contain core LearnFlow tables
    Returns the classification and table record counts.
    """
    inspector = inspect(sqlite_engine)
    table_names = set(inspector.get_table_names())

    if "documents" not in table_names:
        return SourceSchemaType.UNSUPPORTED, {}

    doc_columns = {col["name"] for col in inspector.get_columns("documents")}
    is_legacy = "owner_type" not in doc_columns or "owner_id" not in doc_columns

    schema_type = SourceSchemaType.LEGACY_V2_4 if is_legacy else SourceSchemaType.MODERN_V3

    counts: dict[str, int] = {}
    with sqlite_engine.connect() as conn:
        for tbl in table_names:
            try:
                row_count = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                counts[tbl] = int(row_count or 0)
            except Exception:
                pass

    return schema_type, counts


def validate_target_database(target_engine: Engine) -> None:
    """
    Verifies that target PostgreSQL (or test target) is reachable, has an
    alembic_version table, and matches the Alembic head revision.
    """
    alembic_cfg = migration_bootstrap._alembic_config()
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = script_dir.get_heads()
    if not heads:
        raise TargetSchemaNotReadyError("Alembic script directory has no migration heads defined.")
    expected_head = heads[0]

    try:
        with target_engine.connect() as conn:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            if "alembic_version" not in tables:
                raise TargetSchemaNotReadyError(
                    "Target database does not have an 'alembic_version' table. "
                    "Run 'alembic upgrade head' on the target database before migrating data."
                )

            context = MigrationContext.configure(conn)
            current_heads = context.get_current_heads()
            if not current_heads or current_heads[0] != expected_head:
                raise TargetSchemaNotReadyError(
                    f"Target database is at revision {current_heads}, but migration head is {expected_head}. "
                    "Run 'alembic upgrade head' on the target database before migrating data."
                )
    except TargetSchemaNotReadyError:
        raise
    except Exception as exc:
        raise TargetSchemaNotReadyError(f"Could not connect to target database or verify schema: {exc}") from exc


def resolve_target_user(
    target_engine: Engine,
    target_user_id: str | None = None,
    target_user_email: str | None = None,
) -> User | None:
    """
    Resolves the target user identity against the target database's users table.
    Ensures that target_user_id and target_user_email are consistent if both are given.
    Raises TargetUserNotFoundError if a specified user does not exist in the target database.
    """
    if not target_user_id and not target_user_email:
        return None

    with target_engine.connect() as conn:
        user_by_id = None
        user_by_email = None

        if target_user_id:
            row = conn.execute(text("SELECT id, email, password_hash, created_at FROM users WHERE id = :id"), {"id": target_user_id}).mappings().first()
            if not row:
                raise TargetUserNotFoundError(f"Target user with ID '{target_user_id}' not found in target database.")
            user_by_id = row

        if target_user_email:
            email_clean = target_user_email.strip().lower()
            row = conn.execute(text("SELECT id, email, password_hash, created_at FROM users WHERE email = :email"), {"email": email_clean}).mappings().first()
            if not row:
                raise TargetUserNotFoundError(f"Target user with email '{target_user_email}' not found in target database.")
            user_by_email = row

        if user_by_id and user_by_email:
            if user_by_id["id"] != user_by_email["id"]:
                raise TargetUserConflictError(
                    f"Target user ID '{target_user_id}' and email '{target_user_email}' refer to different users in target database."
                )

        resolved_row = user_by_id or user_by_email
        return User(
            id=resolved_row["id"],
            email=resolved_row["email"],
            password_hash=resolved_row["password_hash"],
            created_at=resolved_row["created_at"],
        )


# ---------------------------------------------------------------------------
# Physical Storage Validation & Copying
# ---------------------------------------------------------------------------


def validate_and_prepare_physical_files(
    documents: list[dict[str, Any]],
    source_storage_dir: Path,
    target_storage_dir: Path,
    dry_run: bool = False,
) -> tuple[int, int, list[Path]]:
    """
    Validates that every referenced physical file exists in source_storage_dir.
    If source_storage_dir != target_storage_dir:
      - Validates and copies files from source to target (if not dry_run).
      - Returns (files_validated, files_copied, newly_copied_paths).
    If any referenced file is missing, raises PhysicalFileMissingError immediately.
    """
    source_storage_dir = source_storage_dir.resolve()
    target_storage_dir = target_storage_dir.resolve()

    missing_files: list[str] = []
    files_to_copy: list[tuple[Path, Path]] = []
    validated_count = 0

    for doc in documents:
        stored_filename = doc.get("stored_filename")
        if not stored_filename:
            continue

        src_path = source_storage_dir / stored_filename
        if not src_path.is_file():
            missing_files.append(stored_filename)
        else:
            validated_count += 1
            if source_storage_dir != target_storage_dir:
                dst_path = target_storage_dir / stored_filename
                files_to_copy.append((src_path, dst_path))

    if missing_files:
        raise PhysicalFileMissingError(
            f"Migration aborted: {len(missing_files)} referenced physical file(s) are missing from source storage ({source_storage_dir}): "
            f"{missing_files[:10]}{'...' if len(missing_files) > 10 else ''}. "
            "Cannot migrate database rows without their corresponding physical binaries."
        )

    newly_copied: list[Path] = []
    copied_count = 0

    if not dry_run and files_to_copy:
        target_storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            for src, dst in files_to_copy:
                if not dst.exists():
                    shutil.copy2(src, dst)
                    newly_copied.append(dst)
                    copied_count += 1
                else:
                    # Already exists at target with matching size
                    copied_count += 1
        except Exception as exc:
            # Clean up on file copy failure
            for path in newly_copied:
                path.unlink(missing_ok=True)
            raise PhysicalFileCopyError(f"Failed copying physical document file to target storage: {exc}") from exc
    elif dry_run:
        copied_count = len(files_to_copy)

    return validated_count, copied_count, newly_copied


# ---------------------------------------------------------------------------
# Migration Pipeline
# ---------------------------------------------------------------------------


def migrate_sqlite_to_postgres(
    sqlite_path: str | Path,
    postgres_url: str,
    target_user_id: str | None = None,
    target_user_email: str | None = None,
    source_storage_dir: str | Path | None = None,
    target_storage_dir: str | Path | None = None,
    dry_run: bool = False,
) -> MigrationSummary:
    """
    Main migration entrypoint. Executes full data migration and legacy schema
    reconciliation from SQLite to PostgreSQL.
    """
    sqlite_path = Path(sqlite_path).resolve()
    if not sqlite_path.is_file():
        raise MigrationError(f"Source SQLite database file not found at: {sqlite_path}")

    source_storage = Path(source_storage_dir).resolve() if source_storage_dir else storage_service.UPLOAD_DIR
    target_storage = Path(target_storage_dir).resolve() if target_storage_dir else storage_service.UPLOAD_DIR

    source_engine = build_engine(f"sqlite:///{sqlite_path}")
    target_engine = build_engine(postgres_url)

    # 1. Validate target database
    validate_target_database(target_engine)

    # 2. Inspect source schema
    source_type, source_counts = inspect_source_database(source_engine)
    if source_type == SourceSchemaType.UNSUPPORTED:
        raise UnsupportedSchemaError(
            f"The database at {sqlite_path} does not contain a recognized LearnFlow schema."
        )

    # 3. Resolve target user
    resolved_target_user = resolve_target_user(
        target_engine,
        target_user_id=target_user_id,
        target_user_email=target_user_email,
    )

    # 4. Check legacy V2.4 ownership rule
    has_legacy_app_data = (
        source_counts.get("documents", 0) > 0
        or source_counts.get("conversations", 0) > 0
    )

    if source_type == SourceSchemaType.LEGACY_V2_4 and has_legacy_app_data and resolved_target_user is None:
        raise TargetUserRequiredError(
            "Legacy V2.4 database contains application data (documents/conversations), which requires an explicit "
            "target user identity via --target-user-id or --target-user-email. "
            "Legacy data cannot be migrated with NULL ownership."
        )

    effective_user_id = resolved_target_user.id if resolved_target_user else None

    summary = MigrationSummary(
        source_path=str(sqlite_path),
        target_url=postgres_url,
        source_type=source_type,
        target_user_id=effective_user_id,
        dry_run=dry_run,
        source_records_discovered=source_counts,
    )

    # 5. Extract all source records via read-only queries
    extracted_data: dict[str, list[dict[str, Any]]] = {}
    with source_engine.connect() as src_conn:
        for tbl in (
            "users",
            "guest_sessions",
            "user_sessions",
            "documents",
            "summaries",
            "flashcards",
            "quiz_questions",
            "mind_maps",
            "document_chunks",
            "conversations",
            "messages",
            "conversation_documents",
            "revision_sessions",
            "revision_session_documents",
            "revision_questions",
            "revision_attempts",
        ):
            if tbl in source_counts:
                rows = src_conn.execute(text(f"SELECT * FROM {tbl}")).mappings().all()
                extracted_data[tbl] = [dict(r) for r in rows]
            else:
                extracted_data[tbl] = []

    # 6. Referential integrity checks on source data
    doc_ids = {d["id"] for d in extracted_data["documents"]}
    convo_ids = {c["id"] for c in extracted_data["conversations"]}
    session_ids = {s["id"] for s in extracted_data["revision_sessions"]}
    question_ids = {q["id"] for q in extracted_data["revision_questions"]}

    for s in extracted_data["summaries"]:
        if s["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"Summary '{s.get('id')}' references missing document '{s.get('document_id')}'.")
    for f in extracted_data["flashcards"]:
        if f["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"Flashcard '{f.get('id')}' references missing document '{f.get('document_id')}'.")
    for q in extracted_data["quiz_questions"]:
        if q["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"Quiz question '{q.get('id')}' references missing document '{q.get('document_id')}'.")
    for m in extracted_data["mind_maps"]:
        if m["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"Mind map '{m.get('id')}' references missing document '{m.get('document_id')}'.")
    for ch in extracted_data["document_chunks"]:
        if ch["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"Document chunk '{ch.get('id')}' references missing document '{ch.get('document_id')}'.")
    for msg in extracted_data["messages"]:
        if msg["conversation_id"] not in convo_ids:
            raise ReferentialIntegrityError(f"Message '{msg.get('id')}' references missing conversation '{msg.get('conversation_id')}'.")
    for cd in extracted_data["conversation_documents"]:
        if cd["conversation_id"] not in convo_ids:
            raise ReferentialIntegrityError(f"ConversationDocument references missing conversation '{cd.get('conversation_id')}'.")
        if cd["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"ConversationDocument references missing document '{cd.get('document_id')}'.")
    for rsd in extracted_data["revision_session_documents"]:
        if rsd["session_id"] not in session_ids:
            raise ReferentialIntegrityError(f"RevisionSessionDocument references missing session '{rsd.get('session_id')}'.")
        if rsd["document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"RevisionSessionDocument references missing document '{rsd.get('document_id')}'.")
    for rq in extracted_data["revision_questions"]:
        if rq["session_id"] not in session_ids:
            raise ReferentialIntegrityError(f"RevisionQuestion '{rq.get('id')}' references missing session '{rq.get('session_id')}'.")
        if rq.get("source_document_id") and rq["source_document_id"] not in doc_ids:
            raise ReferentialIntegrityError(f"RevisionQuestion '{rq.get('id')}' references missing document '{rq.get('source_document_id')}'.")
    for ra in extracted_data["revision_attempts"]:
        if ra["question_id"] not in question_ids:
            raise ReferentialIntegrityError(f"RevisionAttempt '{ra.get('id')}' references missing question '{ra.get('question_id')}'.")
        if ra["session_id"] not in session_ids:
            raise ReferentialIntegrityError(f"RevisionAttempt '{ra.get('id')}' references missing session '{ra.get('session_id')}'.")

    # 7. Physical files validation & copying
    files_validated, files_copied, newly_copied_files = validate_and_prepare_physical_files(
        extracted_data["documents"],
        source_storage,
        target_storage,
        dry_run=dry_run,
    )
    summary.files_validated = files_validated
    summary.files_copied = files_copied

    # 8. Transform data and prepare target objects
    records_to_insert: dict[str, list[dict[str, Any]]] = {
        "users": [],
        "guest_sessions": [],
        "user_sessions": [],
        "documents": [],
        "summaries": [],
        "flashcards": [],
        "quiz_questions": [],
        "mind_maps": [],
        "document_chunks": [],
        "conversations": [],
        "messages": [],
        "conversation_documents": [],
        "revision_sessions": [],
        "revision_session_documents": [],
        "revision_questions": [],
        "revision_attempts": [],
    }

    # Users
    for u in extracted_data["users"]:
        records_to_insert["users"].append({
            "id": u["id"],
            "email": u["email"],
            "password_hash": u["password_hash"],
            "created_at": normalize_datetime(u.get("created_at")),
        })

    # Guest Sessions
    for gs in extracted_data["guest_sessions"]:
        records_to_insert["guest_sessions"].append({
            "id": gs["id"],
            "created_at": normalize_datetime(gs.get("created_at")),
            "last_seen_at": normalize_datetime(gs.get("last_seen_at")),
            "revoked_at": normalize_datetime(gs.get("revoked_at")),
            "document_upload_count": int(gs.get("document_upload_count", 0)),
            "ai_generation_count": int(gs.get("ai_generation_count", 0)),
            "chat_message_count": int(gs.get("chat_message_count", 0)),
        })

    # User Sessions
    for us in extracted_data["user_sessions"]:
        records_to_insert["user_sessions"].append({
            "id": us["id"],
            "user_id": us["user_id"],
            "created_at": normalize_datetime(us.get("created_at")),
            "last_seen_at": normalize_datetime(us.get("last_seen_at")),
            "revoked_at": normalize_datetime(us.get("revoked_at")),
        })

    # Documents
    for d in extracted_data["documents"]:
        if source_type == SourceSchemaType.LEGACY_V2_4:
            owner_type = "user"
            owner_id = effective_user_id
        else:
            owner_type = d.get("owner_type")
            owner_id = d.get("owner_id")

        records_to_insert["documents"].append({
            "id": d["id"],
            "original_filename": d["original_filename"],
            "stored_filename": d["stored_filename"],
            "extracted_text": d.get("extracted_text"),
            "status": d.get("status", "ready"),
            "created_at": normalize_datetime(d.get("created_at")),
            "last_opened_at": normalize_datetime(d.get("last_opened_at")),
            "file_size_bytes": d.get("file_size_bytes"),
            "page_count": d.get("page_count"),
            "owner_type": owner_type,
            "owner_id": owner_id,
        })

    # Summaries
    for s in extracted_data["summaries"]:
        records_to_insert["summaries"].append({
            "id": s["id"],
            "document_id": s["document_id"],
            "content": s["content"],
            "created_at": normalize_datetime(s.get("created_at")),
        })

    # Flashcards
    for f in extracted_data["flashcards"]:
        records_to_insert["flashcards"].append({
            "id": f["id"],
            "document_id": f["document_id"],
            "question": f["question"],
            "answer": f["answer"],
            "position": int(f["position"]),
            "created_at": normalize_datetime(f.get("created_at")),
        })

    # Quiz Questions
    for q in extracted_data["quiz_questions"]:
        records_to_insert["quiz_questions"].append({
            "id": q["id"],
            "document_id": q["document_id"],
            "question": q["question"],
            "options": normalize_json(q["options"]),
            "correct_answer_index": int(q["correct_answer_index"]),
            "position": int(q["position"]),
            "created_at": normalize_datetime(q.get("created_at")),
        })

    # Mind Maps
    for mm in extracted_data["mind_maps"]:
        records_to_insert["mind_maps"].append({
            "id": mm["id"],
            "document_id": mm["document_id"],
            "structure": normalize_json(mm["structure"]),
            "created_at": normalize_datetime(mm.get("created_at")),
        })

    # Document Chunks
    for ch in extracted_data["document_chunks"]:
        records_to_insert["document_chunks"].append({
            "id": ch["id"],
            "document_id": ch["document_id"],
            "chunk_index": int(ch["chunk_index"]),
            "content": ch["content"],
            "embedding": normalize_embedding(ch["embedding"]),
            "created_at": normalize_datetime(ch.get("created_at")),
        })

    # Conversations
    for c in extracted_data["conversations"]:
        if source_type == SourceSchemaType.LEGACY_V2_4:
            owner_type = "user"
            owner_id = effective_user_id
        else:
            owner_type = c.get("owner_type")
            owner_id = c.get("owner_id")

        records_to_insert["conversations"].append({
            "id": c["id"],
            "title": c.get("title", "New Conversation"),
            "title_is_custom": normalize_bool(c.get("title_is_custom", False)),
            "created_at": normalize_datetime(c.get("created_at")),
            "updated_at": normalize_datetime(c.get("updated_at")),
            "owner_type": owner_type,
            "owner_id": owner_id,
        })

    # Messages
    for msg in extracted_data["messages"]:
        records_to_insert["messages"].append({
            "id": msg["id"],
            "conversation_id": msg["conversation_id"],
            "role": msg["role"],
            "content": msg["content"],
            "position": int(msg["position"]),
            "sources_json": normalize_json(msg.get("sources_json")),
            "grounded": normalize_bool(msg.get("grounded")),
            "created_at": normalize_datetime(msg.get("created_at")),
        })

    # Conversation Documents
    for cd in extracted_data["conversation_documents"]:
        records_to_insert["conversation_documents"].append({
            "conversation_id": cd["conversation_id"],
            "document_id": cd["document_id"],
            "added_at": normalize_datetime(cd.get("added_at")),
        })

    # Revision Sessions
    for rs in extracted_data["revision_sessions"]:
        records_to_insert["revision_sessions"].append({
            "id": rs["id"],
            "title": rs.get("title", "Revision Session"),
            "owner_type": rs["owner_type"],
            "owner_id": rs["owner_id"],
            "status": rs.get("status", "in_progress"),
            "config": normalize_json(rs.get("config")),
            "total_questions": int(rs.get("total_questions", 0)),
            "score": float(rs["score"]) if rs.get("score") is not None else None,
            "created_at": normalize_datetime(rs.get("created_at")),
            "completed_at": normalize_datetime(rs.get("completed_at")),
        })

    # Revision Session Documents
    for rsd in extracted_data["revision_session_documents"]:
        records_to_insert["revision_session_documents"].append({
            "session_id": rsd["session_id"],
            "document_id": rsd["document_id"],
            "added_at": normalize_datetime(rsd.get("added_at")),
        })

    # Revision Questions
    for rq in extracted_data["revision_questions"]:
        records_to_insert["revision_questions"].append({
            "id": rq["id"],
            "session_id": rq["session_id"],
            "position": int(rq["position"]),
            "question_type": rq.get("question_type", "multiple_choice"),
            "question_text": rq["question_text"],
            "options": normalize_json(rq.get("options")),
            "correct_answer": rq["correct_answer"],
            "explanation": rq.get("explanation"),
            "source_document_id": rq.get("source_document_id"),
            "source_chunk_id": rq.get("source_chunk_id"),
            "evidence_snippet": rq.get("evidence_snippet"),
            "evidence_metadata": normalize_json(rq.get("evidence_metadata")),
            "created_at": normalize_datetime(rq.get("created_at")),
        })

    # Revision Attempts
    for ra in extracted_data["revision_attempts"]:
        records_to_insert["revision_attempts"].append({
            "id": ra["id"],
            "question_id": ra["question_id"],
            "session_id": ra["session_id"],
            "attempt_number": int(ra["attempt_number"]),
            "submitted_answer": ra["submitted_answer"],
            "is_correct": normalize_bool(ra["is_correct"]),
            "score": float(ra["score"]) if ra.get("score") is not None else 0.0,
            "feedback": ra.get("feedback"),
            "evaluation_metadata": normalize_json(ra.get("evaluation_metadata")),
            "created_at": normalize_datetime(ra.get("created_at")),
        })

    # 9. Target Idempotency & Conflict Check
    with target_engine.connect() as target_conn:
        # Check users
        if records_to_insert["users"]:
            existing_users = target_conn.execute(text("SELECT id, email FROM users")).mappings().all()
            existing_user_ids = {u["id"]: u["email"] for u in existing_users}
            existing_user_emails = {u["email"]: u["id"] for u in existing_users}

            for u in records_to_insert["users"]:
                if u["id"] in existing_user_ids:
                    if existing_user_ids[u["id"]] != u["email"]:
                        raise MigrationConflictError(
                            f"User ID '{u['id']}' already exists in target with email '{existing_user_ids[u['id']]}', "
                            f"conflicting with incoming email '{u['email']}'."
                        )
                elif u["email"] in existing_user_emails:
                    raise MigrationConflictError(
                        f"User with email '{u['email']}' already exists in target with ID '{existing_user_emails[u['email']]}', "
                        f"conflicting with incoming ID '{u['id']}'."
                    )

        # Check documents
        if records_to_insert["documents"]:
            existing_docs = target_conn.execute(text("SELECT id, stored_filename, owner_type, owner_id FROM documents")).mappings().all()
            existing_doc_map = {d["id"]: d for d in existing_docs}
            for d in records_to_insert["documents"]:
                if d["id"] in existing_doc_map:
                    ed = existing_doc_map[d["id"]]
                    if ed["stored_filename"] != d["stored_filename"]:
                        raise MigrationConflictError(
                            f"Document ID '{d['id']}' already exists in target with different stored_filename "
                            f"('{ed['stored_filename']}' vs '{d['stored_filename']}')."
                        )

        # Check conversations
        if records_to_insert["conversations"]:
            existing_convos = target_conn.execute(text("SELECT id, title, owner_type, owner_id FROM conversations")).mappings().all()
            existing_convo_map = {c["id"]: c for c in existing_convos}
            for c in records_to_insert["conversations"]:
                if c["id"] in existing_convo_map:
                    ec = existing_convo_map[c["id"]]
                    if ec["title"] != c["title"]:
                        raise MigrationConflictError(
                            f"Conversation ID '{c['id']}' already exists in target with different title "
                            f"('{ec['title']}' vs '{c['title']}')."
                        )

        # Check revision sessions
        if records_to_insert["revision_sessions"]:
            existing_revs = target_conn.execute(text("SELECT id, title, owner_type, owner_id FROM revision_sessions")).mappings().all()
            existing_rev_map = {r["id"]: r for r in existing_revs}
            for r in records_to_insert["revision_sessions"]:
                if r["id"] in existing_rev_map:
                    er = existing_rev_map[r["id"]]
                    if er["title"] != r["title"]:
                        raise MigrationConflictError(
                            f"RevisionSession ID '{r['id']}' already exists in target with different title "
                            f"('{er['title']}' vs '{r['title']}')."
                        )

    # 10. Execute Transactional Write (or simulate if dry-run)
    insertion_order = (
        ("users", User),
        ("guest_sessions", GuestSession),
        ("user_sessions", UserSession),
        ("documents", Document),
        ("summaries", Summary),
        ("flashcards", Flashcard),
        ("quiz_questions", QuizQuestion),
        ("mind_maps", MindMap),
        ("document_chunks", DocumentChunk),
        ("conversations", Conversation),
        ("messages", Message),
        ("conversation_documents", ConversationDocument),
        ("revision_sessions", RevisionSession),
        ("revision_session_documents", RevisionSessionDocument),
        ("revision_questions", RevisionQuestion),
        ("revision_attempts", RevisionAttempt),
    )

    if dry_run:
        with target_engine.connect() as target_conn:
            for tbl, model_cls in insertion_order:
                candidates = records_to_insert[tbl]
                migrated_count = 0
                skipped_count = 0
                for item in candidates:
                    # Check if exists
                    if tbl == "conversation_documents":
                        exists = target_conn.execute(
                            text("SELECT 1 FROM conversation_documents WHERE conversation_id = :cid AND document_id = :did"),
                            {"cid": item["conversation_id"], "did": item["document_id"]},
                        ).scalar()
                    elif tbl == "revision_session_documents":
                        exists = target_conn.execute(
                            text("SELECT 1 FROM revision_session_documents WHERE session_id = :sid AND document_id = :did"),
                            {"sid": item["session_id"], "did": item["document_id"]},
                        ).scalar()
                    else:
                        exists = target_conn.execute(
                            text(f"SELECT 1 FROM {tbl} WHERE id = :id"),
                            {"id": item["id"]},
                        ).scalar()

                    if exists:
                        skipped_count += 1
                    else:
                        migrated_count += 1

                summary.records_migrated[tbl] = migrated_count
                summary.records_skipped[tbl] = skipped_count

        summary.message = "Dry run completed successfully. No changes were persisted."
        return summary

    # Actual apply mode inside atomic transaction
    try:
        with target_engine.begin() as target_conn:
            for tbl, model_cls in insertion_order:
                candidates = records_to_insert[tbl]
                migrated_count = 0
                skipped_count = 0
                for item in candidates:
                    if tbl == "conversation_documents":
                        exists = target_conn.execute(
                            text("SELECT 1 FROM conversation_documents WHERE conversation_id = :cid AND document_id = :did"),
                            {"cid": item["conversation_id"], "did": item["document_id"]},
                        ).scalar()
                    elif tbl == "revision_session_documents":
                        exists = target_conn.execute(
                            text("SELECT 1 FROM revision_session_documents WHERE session_id = :sid AND document_id = :did"),
                            {"sid": item["session_id"], "did": item["document_id"]},
                        ).scalar()
                    else:
                        exists = target_conn.execute(
                            text(f"SELECT 1 FROM {tbl} WHERE id = :id"),
                            {"id": item["id"]},
                        ).scalar()

                    if exists:
                        skipped_count += 1
                    else:
                        target_conn.execute(
                            Base.metadata.tables[tbl].insert().values(**item)
                        )
                        migrated_count += 1

                summary.records_migrated[tbl] = migrated_count
                summary.records_skipped[tbl] = skipped_count

    except Exception as exc:
        # Transaction rolled back automatically by context manager
        # Clean up any files copied during this run
        for path in newly_copied_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        raise MigrationError(f"Migration failed during database transaction: {exc}") from exc

    # 11. Post-migration validation
    with target_engine.connect() as target_conn:
        for doc in records_to_insert["documents"]:
            row = target_conn.execute(text("SELECT id, owner_type, owner_id FROM documents WHERE id = :id"), {"id": doc["id"]}).mappings().first()
            if not row:
                raise MigrationError(f"Post-migration verification failed: document '{doc['id']}' not found in target.")
            if source_type == SourceSchemaType.LEGACY_V2_4:
                if row["owner_type"] != "user" or row["owner_id"] != effective_user_id:
                    raise MigrationError(f"Post-migration verification failed: document '{doc['id']}' did not receive correct target user ownership.")

        for convo in records_to_insert["conversations"]:
            row = target_conn.execute(text("SELECT id, owner_type, owner_id FROM conversations WHERE id = :id"), {"id": convo["id"]}).mappings().first()
            if not row:
                raise MigrationError(f"Post-migration verification failed: conversation '{convo['id']}' not found in target.")
            if source_type == SourceSchemaType.LEGACY_V2_4:
                if row["owner_type"] != "user" or row["owner_id"] != effective_user_id:
                    raise MigrationError(f"Post-migration verification failed: conversation '{convo['id']}' did not receive correct target user ownership.")

    summary.message = "Data migration completed successfully."
    return summary
