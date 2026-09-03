"""
Tests for POST /conversations/{id}/messages (V2.4 Milestone 2) --
the endpoint that connects a persistent Conversation to the existing,
unchanged chat_service.answer_question(). These tests exercise the new
orchestration (history loading from the database, document-scope
resolution from ConversationDocument, message persistence, sources
snapshotting, error handling) — not retrieval ranking or prompt
construction themselves, which are already covered by test_chat.py,
test_multi_document_chat.py, and test_multi_document_retrieval_intelligence.py.

Fakes follow the same conventions those files already established:
FakeEmbeddingProvider (test_chat.py) for tests that just need
*something* retrievable, and a keyword-based embedding fake
(test_multi_document_chat.py) for the one test here that needs to
prove more than one document actually contributed evidence.
"""

import io
import uuid

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Message
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import NO_CONTEXT_ANSWER

LONG_DOCUMENT_TEXT = "Photosynthesis converts light energy into chemical energy. " * 40
CATS_TEXT = "The cat sat on the mat. " * 60
DOGS_TEXT = "The dog ran in the yard. " * 60


class FakeEmbeddingProvider(EmbeddingProvider):
    """Every text maps to the same vector -- retrieval always returns *something*. See test_chat.py."""

    async def embed_document(self, text: str) -> list[float]:
        return [1.0]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0]


class FailingEmbeddingProvider(EmbeddingProvider):
    """Simulates the embedding service being down."""

    async def embed_document(self, text: str) -> list[float]:
        raise AIProviderError("Simulated embedding provider failure.")

    async def embed_query(self, text: str) -> list[float]:
        raise AIProviderError("Simulated embedding provider failure.")


class KeywordEmbeddingProvider(EmbeddingProvider):
    """
    Cat-dominant vs dog-dominant 2D vectors -- same technique as
    test_multi_document_chat.py's KeywordEmbeddingProvider, needed for
    the multi-document test below to prove both selected documents
    actually contributed chunks, not just that retrieval returned
    something.
    """

    async def embed_document(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        lowered = text.lower()
        cat_count = lowered.count("cat")
        dog_count = lowered.count("dog")
        if cat_count > dog_count:
            return [1.0, 0.0]
        if dog_count > cat_count:
            return [0.0, 1.0]
        return [0.5, 0.5]


class FakeAIProvider(AIProvider):
    """Returns a fixed answer and records every prompt it was called with, in call order."""

    def __init__(self, answer: str = "Photosynthesis converts light into chemical energy.") -> None:
        self._answer = answer
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._answer

    @property
    def last_prompt(self) -> str | None:
        return self.prompts[-1] if self.prompts else None

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    @property
    def chat_prompt(self) -> str | None:
        """
        The prompt actually used to answer the question -- as opposed
        to any *other* call this same shared provider instance may
        have received during the same request. V2.4 Milestone 2 Phase 4
        (automatic conversation naming, conversation_titling.py) also
        calls generate_text on this exact ai_provider, for the first
        message of a conversation, to generate a title -- reusing the
        existing AI provider abstraction rather than introducing a
        second one, per that phase's brief. `last_prompt` above is
        therefore no longer reliably "the chat prompt" on such a
        message; tests that care specifically about what the *chat*
        prompt was grounded in (e.g. which document excerpts it
        contains) should use this instead. Distinguishes a title
        prompt by conversation_titling's own distinctive wording
        ("descriptive title") -- the same "recognize a call site by
        distinctive prompt text" technique
        test_conversational_retrieval.py's ScriptedAIProvider already
        uses for condense-vs-generate.
        """
        chat_prompts = [prompt for prompt in self.prompts if "descriptive title" not in prompt]
        return chat_prompts[-1] if chat_prompts else None


class FailingAIProvider(AIProvider):
    """Simulates the AI service being down."""

    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_and_index_document(client: TestClient, filename: str = "test.pdf", text: str = LONG_DOCUMENT_TEXT) -> str:
    pdf_bytes = _make_test_pdf(text)
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]
    client.post(f"/api/v1/documents/{document_id}/index")
    return document_id


def _create_conversation(client: TestClient, document_ids: list[str]) -> str:
    response = client.post("/api/v1/conversations", json={"document_ids": document_ids})
    assert response.status_code == 201
    return response.json()["id"]


# --- happy path: single document ---------------------------------------


def test_send_message_to_valid_conversation_returns_201_with_both_messages():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "What does photosynthesis convert?"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"] == "Photosynthesis converts light into chemical energy."
    assert body["assistant_message"]["grounded"] is True

    app.dependency_overrides.clear()


def test_user_message_is_persisted():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    db = SessionLocal()
    try:
        user_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id, Message.role == "user")
            .all()
        )
        assert len(user_messages) == 1
        assert user_messages[0].content == "What does photosynthesis convert?"
        assert user_messages[0].sources_json is None
        assert user_messages[0].grounded is None
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_assistant_response_is_persisted():
    fake_ai_provider = FakeAIProvider(answer="Light energy into chemical energy.")
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    db = SessionLocal()
    try:
        assistant_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id, Message.role == "assistant")
            .all()
        )
        assert len(assistant_messages) == 1
        assert assistant_messages[0].content == "Light energy into chemical energy."
        assert assistant_messages[0].grounded is True
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_sources_and_grounding_metadata_is_persisted():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    body = response.json()
    sources = body["assistant_message"]["sources"]
    assert sources is not None
    assert len(sources) > 0
    for source in sources:
        assert source["document_id"] == document_id
        assert source["document_name"] == "test.pdf"
        assert set(["chunk_id", "chunk_index", "content", "score"]).issubset(source.keys())

    # And it round-trips through the database, not just the response.
    db = SessionLocal()
    try:
        assistant_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id, Message.role == "assistant")
            .first()
        )
        assert assistant_message.sources_json is not None
        assert len(assistant_message.sources_json) == len(sources)
        assert assistant_message.sources_json[0]["document_id"] == document_id
    finally:
        db.close()

    app.dependency_overrides.clear()


# --- history -------------------------------------------------------------


def test_conversation_history_is_loaded_from_persisted_messages():
    """
    A second message in the same conversation should have the first
    turn's Q&A available to the model as history -- loaded from the
    database, never resent by the client (there's no `history` field
    on the request body at all).
    """
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )
    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Explain it more simply."},
    )

    # Second call's prompt should include the first turn as history.
    second_prompt = fake_ai_provider.prompts[-1]
    assert "What does photosynthesis convert?" in second_prompt
    assert "Photosynthesis converts light into chemical energy." in second_prompt
    assert "Explain it more simply." in second_prompt
    assert "NOT a source of facts" in second_prompt

    app.dependency_overrides.clear()


def test_first_message_has_no_history_section():
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    assert "Recent conversation" not in fake_ai_provider.last_prompt

    app.dependency_overrides.clear()


# --- ordering --------------------------------------------------------


def test_multiple_messages_maintain_correct_ordering():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": "First question."}
    )
    client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Second question."}
    )

    response = client.get(f"/api/v1/conversations/{conversation_id}")
    messages = response.json()["messages"]

    assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant"]
    assert [message["content"] for message in messages if message["role"] == "user"] == [
        "First question.",
        "Second question.",
    ]
    positions = [message["position"] for message in messages]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)

    app.dependency_overrides.clear()


# --- document scope -------------------------------------------------


def test_conversation_documents_determine_rag_document_scope():
    """
    The conversation's associated document, not any request field,
    determines what gets retrieved -- proven by grounding the prompt
    in that document's actual content.
    """
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    assert "Photosynthesis converts light energy into chemical energy." in fake_ai_provider.chat_prompt

    app.dependency_overrides.clear()


def test_multi_document_conversation_uses_existing_multi_document_retrieval():
    """
    A conversation associated with two documents whose content is
    disjoint (cats vs dogs) should still ground its answer in both --
    the balanced, per-document retrieval behavior already proven for
    POST /documents/chat in test_multi_document_chat.py, now reached
    through the conversation endpoint instead.
    """
    fake_ai_provider = FakeAIProvider(answer="Cats and dogs are both discussed in the excerpts.")
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_document_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)
    dogs_document_id = _upload_and_index_document(client, "dogs.pdf", DOGS_TEXT)
    conversation_id = _create_conversation(client, [cats_document_id, dogs_document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Tell me about cats and dogs."},
    )

    assert response.status_code == 201
    prompt = fake_ai_provider.chat_prompt
    assert "cats.pdf" in prompt
    assert "dogs.pdf" in prompt

    sources = response.json()["assistant_message"]["sources"]
    contributing_document_ids = {source["document_id"] for source in sources}
    assert contributing_document_ids == {cats_document_id, dogs_document_id}

    app.dependency_overrides.clear()


def test_removing_a_document_stops_it_grounding_later_turns_but_keeps_prior_history():
    """
    Phase 7 regression coverage: PUT /conversations/{id}/documents
    (replace_conversation_documents) changes which documents the
    *next* send_message call retrieves against -- see
    _get_conversation_documents_for_chat, which re-reads
    ConversationDocument fresh on every call rather than caching
    anything -- without touching a single already-persisted Message
    row. This was already true by construction (nothing in
    send_message's document-scope resolution or history-loading paths
    depends on what a *previous* turn's document set was), but had no
    end-to-end test naming it directly, and it's one of this phase's
    explicitly called-out regression scenarios ("ensuring removed
    documents no longer provide current-turn RAG context" /
    "preserving previous conversation history after document
    removal").
    """
    fake_ai_provider = FakeAIProvider(answer="Answer.")
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    nebula_document_id = _upload_and_index_document(
        client, "nebula.pdf", "Gravitational collapse of gas clouds forms new stars. " * 40
    )
    coral_document_id = _upload_and_index_document(
        client, "coral.pdf", "Coral reefs support incredibly diverse marine ecosystems. " * 40
    )
    conversation_id = _create_conversation(client, [nebula_document_id])

    first_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "How do nebulae form?"},
    )
    assert first_response.status_code == 201
    assert "gravitational collapse" in fake_ai_provider.chat_prompt.lower()

    # Swap the associated document set entirely: remove the nebula
    # document, add the coral one -- same "here is the full desired
    # set" replace call the frontend's syncSelectedDocuments issues
    # (see ChatPage.jsx).
    replace_response = client.put(
        f"/api/v1/conversations/{conversation_id}/documents",
        json={"document_ids": [coral_document_id]},
    )
    assert replace_response.status_code == 200

    second_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What do coral reefs support?"},
    )
    assert second_response.status_code == 201

    # The removed document's content must not leak into the current
    # turn's retrieved context -- only the newly associated document's
    # excerpts should be present.
    second_prompt = fake_ai_provider.chat_prompt
    assert "gravitational collapse" not in second_prompt.lower()
    assert "gas clouds" not in second_prompt.lower()
    assert "coral reefs" in second_prompt.lower()

    second_sources = second_response.json()["assistant_message"]["sources"]
    assert second_sources
    assert {source["document_id"] for source in second_sources} == {coral_document_id}

    # The first turn's Q&A -- persisted while the nebula document was
    # still associated -- must still be there afterward, both in the
    # just-sent response's implied ordering and in a full GET.
    detail = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert [message["content"] for message in detail["messages"]] == [
        "How do nebulae form?",
        "Answer.",
        "What do coral reefs support?",
        "Answer.",
    ]

    app.dependency_overrides.clear()


# --- error handling ---------------------------------------------------


def test_send_message_to_conversation_with_no_documents_returns_400():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    conversation_id = _create_conversation(client, [])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is this about?"},
    )

    assert response.status_code == 400
    assert "no associated documents" in response.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_send_message_to_missing_conversation_returns_404():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post(
        f"/api/v1/conversations/{uuid.uuid4()}/messages",
        json={"content": "What is this about?"},
    )

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_send_blank_message_returns_422():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": "   "}
    )

    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_send_message_with_unindexed_document_returns_400():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    pdf_bytes = _make_test_pdf(LONG_DOCUMENT_TEXT)
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("unindexed.pdf", pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]
    # Deliberately not indexed.
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is this about?"},
    )

    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_ai_failure_does_not_create_a_false_assistant_response():
    """
    Data-integrity requirement: a failed generation must not leave a
    misleading completed assistant message (or an orphaned user
    message) in the database.
    """
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is this about?"},
    )

    assert response.status_code == 502

    db = SessionLocal()
    try:
        remaining = db.query(Message).filter(Message.conversation_id == conversation_id).count()
        assert remaining == 0
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_embedding_failure_does_not_create_a_false_assistant_response():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FailingEmbeddingProvider()
    client = TestClient(app)
    # Index with a working embedding provider first, then swap in the
    # failing one for the actual message send -- same pattern as
    # test_chat.py's test_chat_returns_502_when_embedding_provider_fails.
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    app.dependency_overrides[get_embedding_provider] = lambda: FailingEmbeddingProvider()
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is this about?"},
    )

    assert response.status_code == 502

    db = SessionLocal()
    try:
        remaining = db.query(Message).filter(Message.conversation_id == conversation_id).count()
        assert remaining == 0
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_conversation_updated_at_bumps_on_message_send():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])
    created = client.get(f"/api/v1/conversations/{conversation_id}").json()

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )

    updated = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert updated["updated_at"] >= created["updated_at"]

    app.dependency_overrides.clear()


# --- timestamp timezone (V2.4 Milestone 2 Phase 3 QA, issue 2) --------
#
# See test_conversations.py's own timestamp-timezone tests for the
# full root-cause explanation (SQLite drops tzinfo on write, so a
# naive datetime read back needs to be re-labeled UTC before Pydantic
# serializes it -- see schemas/conversation.py's `_assume_utc`). This
# extends that same coverage to a persisted Message's `created_at`,
# which goes through MessageResponse rather than
# ConversationSummaryResponse.


def test_message_created_at_carries_explicit_utc_offset():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What does photosynthesis convert?"},
    )
    assert response.status_code == 201
    body = response.json()
    for message in (body["user_message"], body["assistant_message"]):
        value = message["created_at"]
        assert value.endswith("Z") or "+" in value.split("T", 1)[1], (
            f"created_at={value!r} has no explicit UTC offset -- a client's "
            "new Date(...) would parse it as local time, not UTC."
        )

    # GET /conversations/{id} returns the same persisted messages --
    # confirm the fix applies there too, not just the just-sent response.
    fetched = client.get(f"/api/v1/conversations/{conversation_id}").json()
    for message in fetched["messages"]:
        value = message["created_at"]
        assert value.endswith("Z") or "+" in value.split("T", 1)[1]

    app.dependency_overrides.clear()
