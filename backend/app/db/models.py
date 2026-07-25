import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    """
    One uploaded PDF. Every future feature (summary, flashcards, quiz,
    mind map) will store its own results in its own table, linked back
    to a document by this id.
    """

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)

    # The name the user's file had on their computer — shown in the UI.
    original_filename = Column(String, nullable=False)

    # The generated, collision-proof name it's actually saved under on
    # disk (see storage_service.py). Never shown to the user.
    stored_filename = Column(String, nullable=False)

    extracted_text = Column(Text, nullable=True)

    # processing -> ready | failed. A string is enough for V1; if this
    # grows more states, an Enum column would be the next step.
    status = Column(String, nullable=False, default="processing")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Set by POST /documents/{id}/open whenever the user opens this
    # document (see routes_documents.py). Null until opened for the
    # first time. Exists purely to power the "Recently Opened" sort
    # option — nothing else reads it.
    last_opened_at = Column(DateTime, nullable=True)

    # Size of the uploaded file in bytes. Captured once at upload time
    # (see routes_documents.py) rather than stat'd from disk on every
    # request — cheap either way for one document, but this avoids a
    # filesystem call per document on every Document Library load.
    file_size_bytes = Column(Integer, nullable=True)

    # Number of pages, read from the PDF once at upload time (see
    # pdf_service.get_page_count). Unlike file size, this can't be
    # derived cheaply on demand — it requires parsing the PDF's page
    # tree — so it's worth storing rather than recomputing per
    # request. Nullable so existing rows from before this column
    # existed, or documents whose page count couldn't be read, just
    # show nothing instead of erroring.
    page_count = Column(Integer, nullable=True)



class Summary(Base):
    """
    One AI-generated summary of a document. `unique=True` on
    document_id enforces "at most one summary per document" at the
    database level — the service layer also checks this before calling
    the AI, but this is a backstop against race conditions or bugs.
    """

    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, unique=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Flashcard(Base):
    """
    One question/answer pair generated from a document. Many rows per
    document (no unique constraint on document_id, unlike Summary) —
    a normal one-to-many relationship, which is why this is a row per
    card rather than one row holding a JSON list.
    """

    __tablename__ = "flashcards"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    # Preserves the order the AI generated the cards in, since a plain
    # SQL query has no inherent ordering guarantee.
    position = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class QuizQuestion(Base):
    """
    One multiple-choice question generated from a document. Unlike
    Flashcard, `options` is stored as a JSON column on this same row
    rather than a child table — it's a small, fixed-size property OF
    one question, not a separate list of resources, so normalizing it
    into its own table would be a join for four short strings with no
    real benefit.

    correct_answer_index is included here (and in the API response) on
    purpose: without user accounts yet, there's no "quiz attempt" to
    grade server-side against, so grading happens client-side. A
    submit-and-check endpoint that hides this becomes worth building
    once there's a user to attribute an attempt to.
    """

    __tablename__ = "quiz_questions"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list[str]
    correct_answer_index = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MindMap(Base):
    """
    One AI-generated mind map for a document. One-to-one with Document
    (unique=True), like Summary. Stored as a single JSON column holding
    the whole nested tree — {"title": str, "children": [...]} — rather
    than one row per node with a parent_id (an adjacency list). Nothing
    in this product addresses an individual node independently yet, so
    normalizing into rows would be solving a problem V1 doesn't have.
    If a future feature needs to edit one node in place, this is the
    column that would change.
    """

    __tablename__ = "mind_maps"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, unique=True)
    structure = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DocumentChunk(Base):
    """
    One chunk of a document's extracted text, plus the embedding vector
    for that chunk. This is the storage layer of the RAG foundation:
    app/services/rag/chunking.py decides how a document's text gets cut
    into these rows, embedding_service.py fills in `embedding` for each
    one, and retrieval_service.py is what reads them back out again by
    similarity to a query.

    Many rows per document, like Flashcard and QuizQuestion, not one row
    holding a JSON list — retrieval needs to score and rank chunks
    individually, which only works if each one is its own row.

    The embedding is stored as JSON (a plain list of floats) rather than
    a dedicated vector column, extension, or standalone vector database.
    SQLite has no native vector type, and reaching for one (sqlite-vec,
    Chroma, FAISS, pgvector...) would be solving a scale problem
    LearnFlow doesn't have yet: a single user's PDF library, each
    document producing at most a few hundred chunks, comfortably fits in
    memory for the brute-force similarity scan retrieval_service.py
    does. If chunk volume ever grows enough for that scan to be too
    slow, this column — and that one file — are what would change;
    nothing above the retrieval_service function boundary would need to.
    """

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)

    # Preserves the order chunks appeared in the source document.
    # Retrieval ranks by similarity, not this, so nothing reads it yet —
    # kept for the same reason as Flashcard.position: it's cheap to
    # capture now, and a future feature (e.g. showing the passage
    # before/after a match for more context) would need it and
    # shouldn't have to re-derive chunk order from scratch.
    chunk_index = Column(Integer, nullable=False)

    content = Column(Text, nullable=False)

    # list[float]. Every row written by the same embedding model has
    # the same length (3072 numbers for Gemini's gemini-embedding-001
    # at its default output size), but nothing here enforces that
    # length stays consistent — see the note in embedding_service.py
    # about what changing GEMINI_EMBEDDING_MODEL later would require.
    embedding = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
