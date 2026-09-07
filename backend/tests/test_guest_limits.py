"""
V3 Milestone 1 Phase 3: guest usage limits.

Covers app/services/guest_limit_service.py's enforcement end-to-end,
through the HTTP layer: a guest can use each metered action up to its
configured limit, is rejected with a predictable, machine-readable 403
once it's reached, and an authenticated user is exempt from all three
limits entirely. Also covers the two subtleties that make the AI
generation limit correct rather than merely present: a cache hit
(re-fetching content already generated) never counts against it, and
neither does a failed AI call.

Every test that needs to actually *hit* a limit monkeypatches the
relevant `settings.guest_max_*` value down to a small number (2, or 1)
rather than exercising the real configured defaults (guest_max_documents=3,
guest_max_ai_generations=5, guest_max_chat_messages=15 -- see
core/config.py) dozens of times over. That keeps each test's intent
obvious ("two allowed, third rejected") independent of whatever the
real product defaults happen to be tuned to; test_default_guest_limits_match_the_configured_settings
below separately pins down what those real defaults actually are.
"""

import io
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider

SIGNUP_URL = "/api/v1/auth/signup"
UPLOAD_URL = "/api/v1/documents/upload"

VALID_PASSWORD = "Correct-Horse1!"


def _unique_email(label: str) -> str:
    return f"{label}.{datetime.now(timezone.utc).timestamp()}@example.com"


class FakeAIProvider(AIProvider):
    """
    Instant, free, deterministic stand-in for a real provider -- same
    reasoning as every other test file's own copy (see e.g.
    test_summary.py's FakeAIProvider). Returns a single JSON array
    item carrying every key any of summary/flashcards/quiz could ask
    for ("answer" for flashcards, "options"/"correct_answer_index" for
    quiz) -- parse_json_array only checks that its required keys are
    present (see structured_output.py), so extra ones are ignored,
    letting one fixed response satisfy all three endpoints these tests
    call without needing to know in advance which one is asking.
    Summary doesn't parse its response as JSON at all, so the same
    string is equally fine there, just as arbitrary (if odd-looking)
    summary content.
    """

    async def generate_text(self, prompt: str) -> str:
        return (
            '[{"question": "What is 2 + 2?", "answer": "4", '
            '"options": ["3", "4", "5", "6"], "correct_answer_index": 1}]'
        )


class FailingAIProvider(AIProvider):
    """Simulates the AI service being down."""

    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


class CountingAIProvider(AIProvider):
    """Records how many times it was actually asked to generate text --
    lets a test assert the AI was genuinely never called (limit
    rejected before the call) or called exactly once (a cache hit on a
    second request didn't trigger a second call), not just that the
    response looked a certain way."""

    def __init__(self, answer: str = "Fake generated content.") -> None:
        self._answer = answer
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return self._answer


class FakeEmbeddingProvider(EmbeddingProvider):
    """Same reasoning as test_chat.py's own copy -- every text maps to
    the same vector, so retrieval always returns something without
    needing to craft content that ranks a particular way."""

    async def embed_document(self, text: str) -> list[float]:
        return [1.0]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0]


def _make_test_pdf(text: str = "Some content for guest limit tests.") -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload(client: TestClient, filename: str = "test.pdf", text: str | None = None):
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, _make_test_pdf(text or f"Content for {filename}"), "application/pdf")},
    )


def _upload_ready_document(client: TestClient, filename: str = "test.pdf") -> str:
    response = _upload(client, filename)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_and_index_document(client: TestClient, filename: str = "test.pdf") -> str:
    document_id = _upload_ready_document(client, filename)
    index_response = client.post(f"/api/v1/documents/{document_id}/index")
    assert index_response.status_code == 201, index_response.text
    return document_id


def _sign_up(client: TestClient, label: str) -> None:
    response = client.post(
        SIGNUP_URL, json={"email": _unique_email(label), "password": VALID_PASSWORD}
    )
    assert response.status_code == 201, response.text


# --- Document upload limit --------------------------------------------


def test_guest_can_upload_up_to_the_configured_limit(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_documents", 2)
    client = TestClient(app)

    first = _upload(client, "one.pdf")
    second = _upload(client, "two.pdf")

    assert first.status_code == 201
    assert second.status_code == 201


def test_guest_upload_is_rejected_once_the_limit_is_reached(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_documents", 2)
    client = TestClient(app)

    _upload(client, "one.pdf")
    _upload(client, "two.pdf")
    third = _upload(client, "three.pdf")

    assert third.status_code == 403


def test_guest_limit_response_is_predictable_and_machine_readable(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_documents", 1)
    client = TestClient(app)
    _upload(client, "one.pdf")

    response = _upload(client, "two.pdf")

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "guest_limit_reached"
    assert detail["limit_type"] == "document_upload"
    assert detail["limit"] == 1
    assert detail["used"] == 1
    assert isinstance(detail["message"], str) and detail["message"]


def test_rejected_upload_does_not_create_a_document_record(monkeypatch):
    """
    The limit is checked (and the request rejected) before anything is
    written to the database -- a guest at the limit shouldn't end up
    with a stray "processing"/"failed" document from a request that
    was never actually accepted.
    """
    monkeypatch.setattr(settings, "guest_max_documents", 1)
    client = TestClient(app)
    _upload(client, "one.pdf")

    _upload(client, "two.pdf")

    library = client.get("/api/v1/documents")
    assert library.status_code == 200
    assert len(library.json()) == 1


def test_document_upload_limit_persists_across_requests_for_the_same_guest(monkeypatch):
    """
    Usage is tracked on the guest's session, not per-request -- the
    same guest (same cookie jar / TestClient instance) sees its third
    upload rejected within a brand new call, not just cumulatively
    within one request.
    """
    monkeypatch.setattr(settings, "guest_max_documents", 2)
    client = TestClient(app)

    _upload(client, "one.pdf")
    _upload(client, "two.pdf")
    third = _upload(client, "three.pdf")

    assert third.status_code == 403


def test_a_different_guest_session_has_its_own_independent_upload_limit(monkeypatch):
    """
    Guest usage limits are per guest-session, not global -- a second,
    unrelated guest (a fresh TestClient, hence a fresh guest cookie/
    session -- see test_identity_session.py's identical isolation
    setup) starts with a completely fresh allowance, unaffected by how
    much the first guest already used.
    """
    monkeypatch.setattr(settings, "guest_max_documents", 1)
    guest_a = TestClient(app)
    guest_b = TestClient(app)

    _upload(guest_a, "a-one.pdf")
    rejected_for_a = _upload(guest_a, "a-two.pdf")
    allowed_for_b = _upload(guest_b, "b-one.pdf")

    assert rejected_for_a.status_code == 403
    assert allowed_for_b.status_code == 201


def test_authenticated_user_is_not_subject_to_the_document_upload_limit(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_documents", 1)
    client = TestClient(app)
    _sign_up(client, "upload-unlimited")

    first = _upload(client, "one.pdf")
    second = _upload(client, "two.pdf")
    third = _upload(client, "three.pdf")

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201


# --- AI generation limit (summary / flashcards / quiz / mind map) -----


def test_ai_generation_limit_is_shared_across_summary_flashcards_and_quiz(monkeypatch):
    """
    One combined dimension, not one per feature -- see
    guest_limit_service.py's own module docstring for why. Two allowed
    generations (monkeypatched limit) can be any mix of features; the
    third, regardless of which feature it is, is rejected. Exercised
    here with summary, flashcards, and quiz (mind map generation needs
    a differently-shaped AI response -- a JSON object, not an array --
    so it's covered by test_mindmap.py's own suite instead of this
    shared-fake-provider test; the "one shared counter" behavior this
    test checks is a property of guest_limit_service.py, not of any
    one feature, and three of the four is already conclusive).
    """
    monkeypatch.setattr(settings, "guest_max_ai_generations", 2)
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)
    try:
        doc_a = _upload_ready_document(client, "a.pdf")
        doc_b = _upload_ready_document(client, "b.pdf")
        doc_c = _upload_ready_document(client, "c.pdf")

        summary_response = client.post(f"/api/v1/documents/{doc_a}/summary")
        flashcards_response = client.post(f"/api/v1/documents/{doc_b}/flashcards")
        quiz_response = client.post(f"/api/v1/documents/{doc_c}/quiz")

        assert summary_response.status_code == 201
        assert flashcards_response.status_code == 201
        assert quiz_response.status_code == 403
        assert quiz_response.json()["detail"]["limit_type"] == "ai_generation"
    finally:
        app.dependency_overrides.clear()


def test_ai_generation_cache_hit_does_not_count_against_the_limit(monkeypatch):
    """
    Summary/flashcards/quiz/mind map generation is cached (see e.g.
    summary_service.generate_summary_for_document) -- re-requesting a
    summary that already exists must be a free cache hit, never a
    second charge against the guest's AI-generation allowance, and
    never a second real AI call either.
    """
    monkeypatch.setattr(settings, "guest_max_ai_generations", 1)
    counting_provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: counting_provider
    client = TestClient(app)
    try:
        doc_a = _upload_ready_document(client, "a.pdf")
        doc_b = _upload_ready_document(client, "b.pdf")

        first = client.post(f"/api/v1/documents/{doc_a}/summary")
        assert first.status_code == 201
        assert counting_provider.call_count == 1

        # Re-requesting the SAME document's summary is a cache hit --
        # succeeds even though the 1-generation limit is already used.
        cached = client.post(f"/api/v1/documents/{doc_a}/summary")
        assert cached.status_code == 201
        assert counting_provider.call_count == 1
        assert cached.json() == first.json()

        # A genuinely NEW generation, for a different document, is
        # correctly still blocked -- the cache hit above didn't reset
        # or bypass the limit for real usage.
        second_document = client.post(f"/api/v1/documents/{doc_b}/summary")
        assert second_document.status_code == 403
        assert counting_provider.call_count == 1
    finally:
        app.dependency_overrides.clear()


def test_a_failed_ai_generation_does_not_count_against_the_limit(monkeypatch):
    """
    Usage is only recorded after generation actually succeeds -- a
    guest whose one attempt hit a (simulated) AI provider outage still
    has their full allowance to try again once the provider is back.
    """
    monkeypatch.setattr(settings, "guest_max_ai_generations", 1)
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    client = TestClient(app)
    try:
        doc_a = _upload_ready_document(client, "a.pdf")
        failed = client.post(f"/api/v1/documents/{doc_a}/summary")
        assert failed.status_code == 502
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    try:
        retry = client.post(f"/api/v1/documents/{doc_a}/summary")
        assert retry.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_authenticated_user_is_not_subject_to_the_ai_generation_limit(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_ai_generations", 1)
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)
    try:
        _sign_up(client, "generation-unlimited")
        doc_a = _upload_ready_document(client, "a.pdf")
        doc_b = _upload_ready_document(client, "b.pdf")

        first = client.post(f"/api/v1/documents/{doc_a}/summary")
        second = client.post(f"/api/v1/documents/{doc_b}/flashcards")

        assert first.status_code == 201
        assert second.status_code == 201
    finally:
        app.dependency_overrides.clear()


# --- Chat message limit -------------------------------------------------


def test_chat_message_limit_is_shared_across_stateless_and_persisted_chat(monkeypatch):
    """
    One guest chat-message counter, incremented no matter which of the
    app's three "send a chat message" endpoints is used -- a guest
    can't extend their allowance just by switching between the
    stateless single-document endpoint and the persisted conversation
    endpoint.
    """
    monkeypatch.setattr(settings, "guest_max_chat_messages", 1)
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    try:
        document_id = _upload_and_index_document(client, "chat.pdf")

        stateless = client.post(
            f"/api/v1/documents/{document_id}/chat", json={"question": "What is this about?"}
        )
        assert stateless.status_code == 200

        conversation_response = client.post("/api/v1/conversations", json={"document_ids": [document_id]})
        conversation_id = conversation_response.json()["id"]
        persisted = client.post(
            f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Tell me more."}
        )

        assert persisted.status_code == 403
        assert persisted.json()["detail"]["limit_type"] == "chat_message"
    finally:
        app.dependency_overrides.clear()


def test_authenticated_user_is_not_subject_to_the_chat_message_limit(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_chat_messages", 1)
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    try:
        _sign_up(client, "chat-unlimited")
        document_id = _upload_and_index_document(client, "chat.pdf")

        first = client.post(
            f"/api/v1/documents/{document_id}/chat", json={"question": "First question?"}
        )
        second = client.post(
            f"/api/v1/documents/{document_id}/chat", json={"question": "Second question?"}
        )

        assert first.status_code == 200
        assert second.status_code == 200
    finally:
        app.dependency_overrides.clear()


# --- Configured defaults --------------------------------------------------


def test_default_guest_limits_match_the_configured_settings():
    """
    Pins down the actual, real (non-monkeypatched) default limits this
    phase shipped with -- see core/config.py's own comment for the
    reasoning behind these specific numbers. A deliberate change to a
    default should update this test alongside it, not silently drift.
    """
    assert settings.guest_max_documents == 3
    assert settings.guest_max_ai_generations == 5
    assert settings.guest_max_chat_messages == 15
