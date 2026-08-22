import io
import json

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document, Flashcard
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider


class FakeFlashcardProvider(AIProvider):
    """Returns well-formed flashcard JSON, standing in for a real
    provider so tests never call the real Gemini API."""

    async def generate_text(self, prompt: str) -> str:
        return json.dumps(
            [
                {"question": "What is the capital of France?", "answer": "Paris"},
                {"question": "2 + 2?", "answer": "4"},
            ]
        )


class FencedJSONProvider(AIProvider):
    """Simulates a model that wraps JSON in markdown code fences
    despite being told not to — a real, observed failure mode."""

    async def generate_text(self, prompt: str) -> str:
        cards = json.dumps([{"question": "Fenced?", "answer": "Yes"}])
        return f"```json\n{cards}\n```"


class MalformedJSONProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        return "Sure! Here are some flashcards for you: (not actually JSON)"


class FailingAIProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


class CountingAIProvider(AIProvider):
    """Records how many times it was actually asked to generate text,
    so a test can assert the AI was never called for a textless
    document — not just that its output didn't make it into the
    response."""

    def __init__(self):
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return json.dumps([{"question": "Should never be asked", "answer": "N/A"}])


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_ready_document(client: TestClient) -> str:
    pdf_bytes = _make_test_pdf("Some content to turn into flashcards.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def _seed_ready_document_with_text(extracted_text: str) -> str:
    """
    Inserts a "ready" Document row directly, with whatever
    `extracted_text` the test needs — same pattern test_rag.py's
    _seed_ready_document_with_text uses; a document whose extraction
    succeeded but found nothing (or only whitespace) isn't something
    the upload endpoint can produce on demand with a real PDF.
    """
    db = SessionLocal()
    try:
        document = Document(
            original_filename="blank.pdf",
            stored_filename="blank.pdf",
            status="ready",
            extracted_text=extracted_text,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id
    finally:
        db.close()


def _seed_flashcard(document_id: str, question: str, answer: str, position: int = 0) -> None:
    """Inserts a Flashcard row directly, bypassing generation — used
    to simulate one that was already persisted (e.g. generated before
    this guard existed)."""
    db = SessionLocal()
    try:
        db.add(
            Flashcard(
                document_id=document_id, question=question, answer=answer, position=position
            )
        )
        db.commit()
    finally:
        db.close()


def test_create_flashcards_returns_parsed_cards():
    app.dependency_overrides[get_ai_provider] = lambda: FakeFlashcardProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 201
    body = response.json()
    assert len(body) == 2
    assert body[0]["question"] == "What is the capital of France?"
    assert body[0]["position"] == 0
    assert body[1]["position"] == 1

    app.dependency_overrides.clear()


def test_create_flashcards_strips_markdown_code_fences():
    app.dependency_overrides[get_ai_provider] = lambda: FencedJSONProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 201
    assert response.json()[0]["question"] == "Fenced?"

    app.dependency_overrides.clear()


def test_create_flashcards_is_cached_on_second_call():
    app.dependency_overrides[get_ai_provider] = lambda: FakeFlashcardProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    first = client.post(f"/api/v1/documents/{document_id}/flashcards")
    second = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert [card["id"] for card in first.json()] == [card["id"] for card in second.json()]

    app.dependency_overrides.clear()


def test_create_flashcards_returns_502_on_malformed_json():
    app.dependency_overrides[get_ai_provider] = lambda: MalformedJSONProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_flashcards_returns_502_when_provider_fails():
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_flashcards_404_for_missing_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeFlashcardProvider()
    client = TestClient(app)

    response = client.post("/api/v1/documents/does-not-exist/flashcards")

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_get_flashcards_returns_empty_list_before_generation():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.get(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 200
    assert response.json() == []


def test_get_flashcards_404_for_missing_document():
    client = TestClient(app)

    response = client.get("/api/v1/documents/does-not-exist/flashcards")

    assert response.status_code == 404


def test_create_flashcards_422_for_document_with_no_readable_text():
    """
    A document can reach "ready" (extraction completed without
    raising) while extracted_text is still blank — e.g. a scanned or
    image-only file OCR found no readable characters in. Generating
    flashcards for it should say so clearly rather than sending an
    empty document to the AI, which would otherwise invent flashcards
    about whatever topic it wants instead of the document.
    """
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_create_flashcards_422_for_whitespace_only_text():
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("   \n\t  ")

    response = client.post(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_get_flashcards_422_for_document_with_no_readable_text():
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.get(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()


def test_get_flashcards_422_even_with_stale_cached_flashcards():
    """
    A Flashcard set that already exists for a document (e.g. generated
    before this guard existed) must not be served back once the
    document itself has no readable text — GET must refuse the same
    way POST does, not quietly return the stale set as if it were
    valid, document-derived content.
    """
    document_id = _seed_ready_document_with_text("")
    _seed_flashcard(document_id, "Stale question?", "Stale answer.")

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{document_id}/flashcards")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
