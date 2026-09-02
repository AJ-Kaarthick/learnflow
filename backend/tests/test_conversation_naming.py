"""
Tests for automatic conversation naming (V2.4 Milestone 2 Phase 4),
wired into POST /conversations/{id}/messages -- see that route's own
docstring in routes_conversations.py for the full design. These tests
exercise the *route-level* orchestration (when generation is
attempted, the race-condition protection around writing a generated
title, best-effort failure handling, what's returned to the frontend)
-- not title text quality or sanitization itself, which is already
covered in isolation by test_conversation_titling.py.

Fakes follow the same conventions test_conversation_messages.py
already established (FakeEmbeddingProvider, a fixed-answer
FakeAIProvider), extended here with providers that can tell a
title-generation prompt apart from a normal chat-answer prompt -- the
same "recognize a call site by distinctive prompt text" technique
test_conversational_retrieval.py's ScriptedAIProvider uses for
condense-vs-generate. conversation_titling._TITLE_INSTRUCTIONS' literal
phrase "descriptive title" is what makes that possible; see this file's
_is_title_prompt helper.
"""

import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Conversation, Message
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider

DOCUMENT_TEXT = "Photosynthesis converts light energy into chemical energy. " * 40


def _is_title_prompt(prompt: str) -> bool:
    """Mirrors conversation_titling._TITLE_INSTRUCTIONS' distinctive wording."""
    return "descriptive title" in prompt


class FakeEmbeddingProvider(EmbeddingProvider):
    """Every text maps to the same vector -- retrieval always returns *something*. See test_chat.py."""

    async def embed_document(self, text: str) -> list[float]:
        return [1.0]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0]


class TitleAwareAIProvider(AIProvider):
    """
    Returns a scripted chat answer for a normal chat/condense prompt,
    and a separately scripted title for a title-generation prompt --
    recognizing which is which by _is_title_prompt, the same technique
    test_conversational_retrieval.py's ScriptedAIProvider uses to tell
    condense-vs-generate calls apart. Records every prompt (in order)
    and how many of them were title-generation calls specifically, so
    tests can assert title generation was attempted exactly once (or
    not at all) without depending on overall call order.
    """

    def __init__(
        self,
        title: str = "Photosynthesis Basics",
        answer: str = "Photosynthesis converts light into chemical energy.",
    ) -> None:
        self._title = title
        self._answer = answer
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if _is_title_prompt(prompt):
            return self._title
        return self._answer

    @property
    def title_call_count(self) -> int:
        return sum(1 for prompt in self.prompts if _is_title_prompt(prompt))

    @property
    def last_title_prompt(self) -> str | None:
        """The most recent title-generation prompt, for tests that need to inspect its content."""
        title_prompts = [prompt for prompt in self.prompts if _is_title_prompt(prompt)]
        return title_prompts[-1] if title_prompts else None


class FailingTitleAIProvider(AIProvider):
    """Chat/condense prompts succeed normally; a title-generation prompt raises."""

    def __init__(self, answer: str = "Photosynthesis converts light into chemical energy.") -> None:
        self._answer = answer
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if _is_title_prompt(prompt):
            raise AIProviderError("Simulated title-generation failure.")
        return self._answer


class BlankTitleAIProvider(AIProvider):
    """Chat/condense prompts succeed normally; a title-generation prompt returns unusable output."""

    def __init__(
        self,
        blank_title: str = '   ""   ',
        answer: str = "Photosynthesis converts light into chemical energy.",
    ) -> None:
        self._blank_title = blank_title
        self._answer = answer
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if _is_title_prompt(prompt):
            return self._blank_title
        return self._answer


class RenamingMidGenerationAIProvider(AIProvider):
    """
    Simulates the exact race this phase's brief calls out: "A user
    could rename a conversation while automatic title generation is in
    progress." When asked for a title, this reaches into the database
    through a *separate* session/transaction first -- exactly as a
    concurrent PATCH /conversations/{id} request would, landing its
    own commit before this one's -- and only then returns the
    generated title text, so send_message's guarded write
    (_apply_generated_title_if_still_default) has to contend with a
    title_is_custom that already flipped to True by the time it runs.
    """

    def __init__(
        self,
        conversation_id: str,
        racing_title: str = "User's Manual Title",
        title: str = "Photosynthesis Basics",
        answer: str = "Photosynthesis converts light into chemical energy.",
    ) -> None:
        self._conversation_id = conversation_id
        self._racing_title = racing_title
        self._title = title
        self._answer = answer

    async def generate_text(self, prompt: str) -> str:
        if _is_title_prompt(prompt):
            db = SessionLocal()
            try:
                conversation = db.query(Conversation).filter(Conversation.id == self._conversation_id).first()
                conversation.title = self._racing_title
                conversation.title_is_custom = True
                db.commit()
            finally:
                db.close()
            return self._title
        return self._answer


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_and_index_document(client: TestClient, filename: str = "test.pdf", text: str = DOCUMENT_TEXT) -> str:
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


def _send_message(client: TestClient, conversation_id: str, content: str):
    return client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"content": content})


# --- automatic title generation after the first meaningful message -----


def test_first_message_generates_and_returns_title():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = _send_message(client, conversation_id, "What does photosynthesis convert?")

    assert response.status_code == 201
    assert response.json()["generated_title"] == "Photosynthesis Basics"
    assert provider.title_call_count == 1

    app.dependency_overrides.clear()


def test_generated_title_is_persisted():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    _send_message(client, conversation_id, "What does photosynthesis convert?")

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "Photosynthesis Basics"
        assert conversation.title_is_custom is False
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_generated_title_is_returned_to_the_frontend_via_get():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    _send_message(client, conversation_id, "What does photosynthesis convert?")

    fetched = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert fetched["title"] == "Photosynthesis Basics"
    assert fetched["title_is_custom"] is False

    listed = client.get("/api/v1/conversations").json()
    listed_entry = next(c for c in listed if c["id"] == conversation_id)
    assert listed_entry["title"] == "Photosynthesis Basics"

    app.dependency_overrides.clear()


# --- second message never regenerates ------------------------------------


def test_second_message_does_not_regenerate_title():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    first = _send_message(client, conversation_id, "What does photosynthesis convert?")
    assert first.json()["generated_title"] == "Photosynthesis Basics"

    second = _send_message(client, conversation_id, "Tell me more.")
    assert second.status_code == 201
    assert second.json()["generated_title"] is None
    # Exactly one of the (possibly several) AI calls made across both
    # sends was a title-generation call -- the second send's own chat
    # call doesn't count, and no second title attempt was made either.
    assert provider.title_call_count == 1

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "Photosynthesis Basics"
    finally:
        db.close()

    app.dependency_overrides.clear()


# --- manual rename is never overwritten -----------------------------------


def test_manual_rename_before_first_message_is_never_overwritten():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    rename_response = client.patch(
        f"/api/v1/conversations/{conversation_id}", json={"title": "My custom title"}
    )
    assert rename_response.status_code == 200

    response = _send_message(client, conversation_id, "What does photosynthesis convert?")

    assert response.status_code == 201
    assert response.json()["generated_title"] is None
    # Renamed *before* the first message, so title generation should
    # never even have been attempted -- "avoid unnecessary AI calls."
    assert provider.title_call_count == 0

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "My custom title"
        assert conversation.title_is_custom is True
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_manual_rename_after_first_message_is_preserved_on_second_message():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    _send_message(client, conversation_id, "What does photosynthesis convert?")
    client.patch(f"/api/v1/conversations/{conversation_id}", json={"title": "My custom title"})

    response = _send_message(client, conversation_id, "Tell me more.")

    assert response.status_code == 201
    assert response.json()["generated_title"] is None

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "My custom title"
        assert conversation.title_is_custom is True
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_race_condition_rename_during_title_generation_is_not_overwritten():
    """
    The exact race this phase's brief calls out: a rename that lands
    *while* the AI title-generation call for this same first message is
    still in flight must win -- see RenamingMidGenerationAIProvider and
    _apply_generated_title_if_still_default's own docstring in
    routes_conversations.py.
    """
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    provider = RenamingMidGenerationAIProvider(
        conversation_id=conversation_id, racing_title="User's Manual Title"
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider

    response = _send_message(client, conversation_id, "What does photosynthesis convert?")

    assert response.status_code == 201
    # The AI-generated title lost the race -- never reported to the frontend.
    assert response.json()["generated_title"] is None

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "User's Manual Title"
        assert conversation.title_is_custom is True
    finally:
        db.close()

    app.dependency_overrides.clear()


# --- best-effort: title-generation failure never fails the chat request --


def test_title_generation_failure_does_not_fail_chat_request():
    provider = FailingTitleAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = _send_message(client, conversation_id, "What does photosynthesis convert?")

    assert response.status_code == 201
    body = response.json()
    assert body["assistant_message"]["content"] == "Photosynthesis converts light into chemical energy."
    assert body["generated_title"] is None

    app.dependency_overrides.clear()


def test_title_generation_failure_leaves_no_orphaned_or_inconsistent_messages():
    provider = FailingTitleAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    _send_message(client, conversation_id, "What does photosynthesis convert?")

    db = SessionLocal()
    try:
        messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()
        assert len(messages) == 2
        roles = {message.role for message in messages}
        assert roles == {"user", "assistant"}

        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "New Conversation"
        assert conversation.title_is_custom is False
    finally:
        db.close()

    app.dependency_overrides.clear()


def test_blank_generated_title_is_handled_safely():
    provider = BlankTitleAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])

    response = _send_message(client, conversation_id, "What does photosynthesis convert?")

    assert response.status_code == 201
    body = response.json()
    assert body["assistant_message"]["content"] == "Photosynthesis converts light into chemical energy."
    assert body["generated_title"] is None

    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation.title == "New Conversation"
        assert conversation.title_is_custom is False

        messages = db.query(Message).filter(Message.conversation_id == conversation_id).all()
        assert len(messages) == 2
    finally:
        db.close()

    app.dependency_overrides.clear()


# --- independence across conversations ------------------------------------


def test_two_conversations_generate_titles_independently():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_a = _create_conversation(client, [document_id])
    conversation_b = _create_conversation(client, [document_id])

    response_a = _send_message(client, conversation_a, "What does photosynthesis convert?")
    # Rename B manually before it ever gets a message.
    client.patch(f"/api/v1/conversations/{conversation_b}", json={"title": "Custom B title"})
    response_b = _send_message(client, conversation_b, "What does photosynthesis convert?")

    assert response_a.json()["generated_title"] == "Photosynthesis Basics"
    assert response_b.json()["generated_title"] is None

    db = SessionLocal()
    try:
        conv_a = db.query(Conversation).filter(Conversation.id == conversation_a).first()
        conv_b = db.query(Conversation).filter(Conversation.id == conversation_b).first()
        assert conv_a.title == "Photosynthesis Basics"
        assert conv_a.title_is_custom is False
        assert conv_b.title == "Custom B title"
        assert conv_b.title_is_custom is True
    finally:
        db.close()

    app.dependency_overrides.clear()


# --- updated_at behavior is preserved -------------------------------------


def test_updated_at_still_bumps_when_a_title_is_also_generated():
    provider = TitleAwareAIProvider(title="Photosynthesis Basics")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client)
    conversation_id = _create_conversation(client, [document_id])
    created = client.get(f"/api/v1/conversations/{conversation_id}").json()

    _send_message(client, conversation_id, "What does photosynthesis convert?")

    updated = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert updated["updated_at"] >= created["updated_at"]
    assert updated["title"] == "Photosynthesis Basics"

    app.dependency_overrides.clear()


# --- document filenames passed as naming context (naming follow-up) ------
#
# These exercise the route-level plumbing added on top of the existing
# best-effort/race-safety design above: does send_message actually hand the
# conversation's document filenames to generate_conversation_title, in the
# right shape, for the scenarios the brief called out. TitleAwareAIProvider
# still returns a fixed scripted title regardless of prompt content (real
# title *quality* -- e.g. "would a live model actually skip the filename
# here" -- isn't something a scripted fake can verify; that's exactly why
# _TITLE_INSTRUCTIONS' actual usage rules are unit-tested in isolation in
# test_conversation_titling.py). What's verified here is that the right
# information reaches the prompt for each scenario, via last_title_prompt.


def test_title_prompt_includes_filename_when_message_topic_is_already_self_evident():
    """
    Scenario 1: a first message whose topic is already clear on its own
    (naming its subject directly) -- the single selected document's
    filename still reaches the prompt as context (the route always offers
    it), but _TITLE_INSTRUCTIONS' own rules -- unit-tested separately --
    are what tell the model not to blindly fold the filename into the
    title when the message doesn't need it.
    """
    provider = TitleAwareAIProvider(title="DDL & DML Definitions")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, filename="EX-DDL&DML.docx")
    conversation_id = _create_conversation(client, [document_id])

    response = _send_message(
        client, conversation_id, "does the ddl & dml document have its definition"
    )

    assert response.status_code == 201
    assert response.json()["generated_title"] == "DDL & DML Definitions"
    prompt = provider.last_title_prompt
    assert "does the ddl & dml document have its definition" in prompt
    assert "EX-DDL&DML.docx" in prompt
    # The instruction that stops a filename from being blindly folded in
    # whenever the message already carries the topic.
    assert "If the message already makes the topic clear on its own" in prompt


def test_title_prompt_includes_filename_context_for_a_vague_message():
    """
    Scenario 2: a vague first message ("how many credits is this for") that
    says nothing about its own topic -- the selected document's filename
    must reach the prompt, since it's the only available signal for what
    "this" refers to.
    """
    provider = TitleAwareAIProvider(title="Timetable Credit Inquiry")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, filename="Timetable final 1.pdf")
    conversation_id = _create_conversation(client, [document_id])

    response = _send_message(client, conversation_id, "how many credits is this for")

    assert response.status_code == 201
    assert response.json()["generated_title"] == "Timetable Credit Inquiry"
    prompt = provider.last_title_prompt
    assert "how many credits is this for" in prompt
    assert "Timetable final 1.pdf" in prompt


def test_title_prompt_includes_both_filenames_for_a_comparison_message():
    """
    Scenario 3: two documents selected and a message that explicitly asks
    to compare them -- both filenames must reach the prompt, and the
    instruction permitting a comparison-style title must be present.
    """
    provider = TitleAwareAIProvider(title="Timetable vs Serverless Computing")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_a = _upload_and_index_document(client, filename="Timetable final 1.pdf")
    document_b = _upload_and_index_document(
        client, filename="Module_01_serverless_computing_Lec01.pptx"
    )
    conversation_id = _create_conversation(client, [document_a, document_b])

    response = _send_message(
        client, conversation_id, "how do the documents differ from each other?"
    )

    assert response.status_code == 201
    assert response.json()["generated_title"] == "Timetable vs Serverless Computing"
    prompt = provider.last_title_prompt
    assert "Timetable final 1.pdf" in prompt
    assert "Module_01_serverless_computing_Lec01.pptx" in prompt
    assert "the title may reflect that comparison" in prompt


def test_title_prompt_does_not_force_every_filename_when_message_is_about_one_topic():
    """
    Scenario 4: two documents selected, but the first message is about only
    one self-contained topic and never references "the documents"
    collectively -- both filenames still reach the prompt as available
    context (the route doesn't try to guess relevance itself, and always
    offers everything selected), but the rule instructing the model to
    leave out documents the message doesn't concern must also be present,
    which is what actually keeps them from being forced into the title.
    """
    provider = TitleAwareAIProvider(title="DDL & DML Definitions")
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_a = _upload_and_index_document(client, filename="EX-DDL&DML.docx")
    document_b = _upload_and_index_document(client, filename="Timetable final 1.pdf")
    conversation_id = _create_conversation(client, [document_a, document_b])

    response = _send_message(
        client, conversation_id, "does the ddl & dml document have its definition"
    )

    assert response.status_code == 201
    assert response.json()["generated_title"] == "DDL & DML Definitions"
    prompt = provider.last_title_prompt
    assert "EX-DDL&DML.docx" in prompt
    assert "Timetable final 1.pdf" in prompt
    assert (
        "If several documents are selected but the message only concerns "
        "one of them" in prompt
    )
