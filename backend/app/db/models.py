import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    """
    One uploaded document (PDF or DOCX — see
    document_extraction_service.py for how the text below gets read
    out of either). Every feature (summary, flashcards, quiz, mind
    map) stores its own results in its own table, linked back to a
    document by this id, and none of them care which file format this
    document actually was — they only ever read `extracted_text`.
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

    # Number of pages, read once at upload time for formats that have
    # a well-defined one (currently just PDF — see
    # document_extraction_service.get_page_count). Unlike file size,
    # this can't be derived cheaply on demand for PDF — it requires
    # parsing the page tree — so it's worth storing rather than
    # recomputing per request. Nullable so existing rows from before
    # this column existed, documents whose page count couldn't be
    # read, and documents in a format with no page count at all (e.g.
    # DOCX, which has no page tree — pagination there depends on
    # fonts/margins, not anything stored in the file) just show
    # nothing instead of erroring.
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


class Conversation(Base):
    """
    A persistent chat thread (V2.4 Milestone 2). This is the entity
    that replaces the old document-set-derived "conversation" the
    frontend used to synthesize from `sorted(selectedDocumentIds).join(",")`
    — identity now lives here, as a real row, independent of which
    documents happen to be selected at any given moment.

    `title` always has a value (never null) — new conversations start
    with a plain fallback ("New Conversation") so the UI never needs a
    null-title rendering branch. `title_is_custom` is the entire
    mechanism protecting a user's manual rename from ever being
    overwritten by AI auto-titling: PATCH /conversations/{id} sets it
    to True unconditionally, and nothing else is allowed to flip it
    back to False. Whatever writes an AI-generated title (Milestone 3)
    must re-check this flag immediately before its own commit, so a
    rename racing an in-flight title generation always wins regardless
    of which one started first.

    `updated_at` is deliberately NOT wired to SQLAlchemy's `onupdate`
    (which would bump it on *any* attribute change, including a
    rename) — it's meant to track conversation *activity* specifically
    for "most recently active first" ordering (see GET /conversations),
    not "most recently edited." Nothing in this milestone changes it
    after creation; Milestone 2 (message persistence) is what will
    bump it whenever a new message is sent.

    No relationship()/cascade is configured here to Message or
    ConversationDocument, matching this file's existing convention
    (see Document's docstring above) — deletion cleans up both
    explicitly in the route layer instead (see
    routes_conversations.delete_conversation).
    """

    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, nullable=False, default="New Conversation")
    title_is_custom = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Message(Base):
    """
    One turn (user question or assistant answer) in a Conversation.
    Many rows per conversation, like Flashcard/QuizQuestion/DocumentChunk
    are many rows per document — not one row holding a JSON list —
    since a conversation's turns need to be queried, ordered, and
    (later) trimmed to the most recent N independently.

    `position` is an explicit, monotonically increasing integer per
    conversation, not derived from `created_at` — same reasoning as
    Flashcard.position's docstring: "a plain SQL query has no inherent
    ordering guarantee." Assigned by the route/service that creates a
    message (max(position) + 1 for that conversation), not by the
    database.

    `sources_json` snapshots the grounding chunks an assistant message
    was based on (chunk id/index/content/score, plus which document
    each came from) at the moment the answer was generated — the same
    "small, fixed-size property OF one row" reasoning QuizQuestion.options
    and MindMap.structure already use for storing structured data as a
    single JSON column rather than a child table. Snapshotting rather
    than looking sources up live is what lets an old message keep
    showing its citations correctly even after the document they came
    from is later deleted (see delete_document in routes_documents.py —
    it only removes that document's ConversationDocument rows, never
    touches Message). Null for user messages, and for assistant
    messages generated with no retrieved context at all.

    `grounded` mirrors ChatResponse.grounded for the same message. Null
    for user messages.

    Nothing writes to this table yet as of Milestone 1 (backend
    foundation only) — POST /conversations/{id}/messages, which
    creates these rows by calling the existing, unchanged
    chat_service.answer_question(), is Milestone 2.
    """

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant" -- validated at the Pydantic layer, same as Document.status is a plain string here and an Enum only at the API boundary
    content = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    sources_json = Column(JSON, nullable=True)
    grounded = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GuestSession(Base):
    """
    A temporary guest identity (V3 Milestone 1 Phase 1). This is the
    server-side half of the "who is making this request?" question —
    see app/schemas/identity.py for the request-facing Identity value
    built from a row here, and app/api/deps.py:get_current_identity
    for how a request gets resolved to one.

    `id` is NOT a generate_uuid() resource id like every other table's
    primary key in this file — it's a high-entropy bearer token (see
    guest_session_service.generate_session_token), because this value
    doubles as the session credential itself: whoever holds it (via
    the httponly cookie it's issued in) *is* this guest, the same way
    holding a login session's cookie value makes you that logged-in
    user. Deliberately not put in a separate "token" column with a
    generate_uuid() `id` alongside it — there is no second use for a
    non-secret identifier here yet (nothing joins against GuestSession
    the way document_id joins against Document), and adding one now
    would be exactly the kind of speculative structure this phase's
    brief says to avoid. If Milestone 2's ownership model ends up
    needing a stable identifier that's safe to reference elsewhere
    without exposing the credential (e.g. as a foreign key on future
    guest-owned rows), that's a natural, additive change to make then.

    No relationship to Document/Conversation/etc. yet — this phase
    establishes identity only ("who is making this request?"), not
    ownership ("what data does this identity own?"). That's explicitly
    Milestone 2 Phase 4's job (see this phase's brief); wiring a
    guest_session_id foreign key onto existing tables now would be
    scope creep this phase was told not to do.

    Expiration is computed, not stored: a session is valid as long as
    `last_seen_at` is more recent than
    `settings.guest_session_inactivity_minutes` ago (see
    guest_session_service.get_valid_guest_session). There's
    deliberately no separate `expires_at` column that would need to be
    kept in sync with that setting and with every `last_seen_at`
    update — one column, one source of truth.

    `revoked_at` supports explicit invalidation (e.g. a future
    guest-to-account migration in Phase 2 retiring the guest session
    it migrated data out of) without deleting the row outright while
    that data might still be worth auditing. Nothing sets it yet in
    this phase.
    """

    __tablename__ = "guest_sessions"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Bumped on every request that resolves to this session (see
    # guest_session_service.touch_guest_session) -- this sliding
    # window, not created_at, is what expiration is measured against,
    # so an actively-used guest session never expires mid-study-session
    # purely because it's been open a long time.
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    revoked_at = Column(DateTime, nullable=True)


class User(Base):
    """
    A registered account (V3 Milestone 1 Phase 2). This is the durable
    counterpart to GuestSession: a GuestSession *is* its own identity
    (the token is the credential), but a User is a stable identity a
    person can return to from any browser, authenticated by a
    separate credential (a password, checked against `password_hash`)
    rather than merely by possessing an opaque token.

    Deliberately minimal, per this phase's brief -- just enough to
    authenticate someone and know which stable id they are. No
    profile fields (display name, avatar, ...), no email verification
    flag, no password-reset token -- all explicitly out of scope for
    this phase. Milestone 2 is what will give a User rows to own
    (Documents, Conversations, ...); this table only establishes that
    the identity exists.

    `email` is the login identifier (this project's "appropriate
    choice" per the brief -- there's no username concept anywhere
    else in the app to reuse instead). Stored lowercased (see
    schemas/auth.py's validators) so uniqueness and lookup are
    case-insensitive without needing a database-level
    citext/lower(email) index -- SQLite has neither, and this project
    isn't moving off SQLite this phase (that's Milestone 2). `unique=True`
    is the database-level backstop against duplicate accounts; the
    service layer (auth_service.get_user_by_email) also checks this
    before insert, same "backstop against race conditions" pattern as
    Summary.document_id and ConversationDocument's composite key
    elsewhere in this file.

    `password_hash` is a bcrypt hash (see auth_service.hash_password)
    -- never the plaintext password, never a reversible encryption of
    it. There is no column here that could leak a recoverable
    password even if this table were dumped outright.

    Forward-compatibility notes for future authentication work (not
    implemented in this phase, per the brief):

    - Email verification: `password_hash` being nullable-in-spirit-only
      (every row has one, since password auth is the only signup path
      today) is exactly what will need to loosen if a future phase
      adds "sign up, verify by email" as a *second* path -- but that's
      a column addition (`email_verified: bool`, defaulting False) and
      a token/expiry table, not a change to this table's shape or to
      `id`/`email` as the stable identity a session or a future
      ownership FK (Milestone 2) points at.
    - An OAuth provider (e.g. "Continue with Google"): this table's
      `id` already exists independently of *how* someone authenticates
      -- a future `oauth_identities` table (provider, provider_user_id,
      user_id FK -> this table) could let a `User` be reached via a
      password, an OAuth login, or both, without this table needing a
      `password_hash`-shaped column for every future login method or
      any change to how `UserSession`/`Identity` represent "which User
      is this". Account-linking rules (what happens if someone signs
      up with a password, then later hits "Continue with Google" with
      the same email) are a decision for whenever that phase actually
      lands, not one this table forecloses today.
    """

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserSession(Base):
    """
    An authenticated session (V3 Milestone 1 Phase 2) -- the User
    equivalent of GuestSession, and deliberately shaped to match it:
    `id` is itself the high-entropy bearer token (see
    user_session_service.generate_session_token), not a
    generate_uuid() resource id, for exactly the same reason
    GuestSession's docstring gives -- holding this value (via the
    httponly cookie it's issued in) *is* being authenticated as
    `user_id`. Expiration is likewise computed from `last_seen_at`
    against a settings value (`user_session_inactivity_days`, longer
    than a guest's -- "stay signed in across a browser refresh /
    normal return visit" is exactly what an authenticated session is
    for) rather than a stored `expires_at`, and `revoked_at` exists so
    logout can invalidate a session without deleting the row outright
    (see user_session_service.delete_user_session, which -- like its
    guest counterpart -- currently just deletes rather than setting
    this; kept as a column for the same future-proofing reason
    GuestSession keeps one).

    Kept as its own table, with its own cookie (see
    core/config.py:user_session_cookie_name), rather than reusing
    GuestSession itself: a guest session and an authenticated session
    are different credentials with different lifetimes and different
    trust levels (see api/deps.py:get_current_identity, which checks
    this table first and only falls back to guest resolution when no
    valid row here is presented) -- conflating them into one table
    would mean either weakening guest sessions' short inactivity
    window to match a signed-in user's, or vice versa, and would make
    "is this request authenticated or just a guest?" a property you'd
    have to check a nullable column for instead of "which table did
    this token resolve in".

    No relationship()/cascade to User -- same convention as every
    other foreign key in this file (see Message's docstring); a
    session row is looked up by id and its `user_id` queried
    separately (see api/deps.py) rather than traversed via an ORM
    relationship.
    """

    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)


class ConversationDocument(Base):
    """
    Join table linking a Conversation to the Documents it references —
    a plain many-to-many, the same document can be associated with any
    number of conversations and a conversation can reference any number
    of documents. Composite primary key on (conversation_id, document_id)
    enforces "a document can only be associated with a given
    conversation once" at the database level — the same "backstop
    against race conditions or bugs" reasoning as Summary's
    `unique=True` on document_id, just extended to a two-column key
    here since this table's natural identity is the pair, not either
    column alone.

    `added_at` gives conversation-document chips a stable, predictable
    order (oldest-added-first) without needing a separate explicit
    `position` column, the way Message needs one. PUT
    /conversations/{id}/documents (replace-the-set) deletes and
    re-inserts rows on every call rather than diffing, which does mean
    a document's `added_at` resets if it's removed and re-added later
    or simply re-sent in a later PUT — an accepted, minor simplicity
    trade-off, not a correctness issue (see routes_conversations.py).

    No relationship()/cascade configured — deletion cleanup lives in
    the route layer on both sides: delete_conversation removes this
    conversation's rows, and delete_document (routes_documents.py)
    removes this document's rows, exactly like every other child table
    Document already has.
    """

    __tablename__ = "conversation_documents"

    conversation_id = Column(String, ForeignKey("conversations.id"), primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
