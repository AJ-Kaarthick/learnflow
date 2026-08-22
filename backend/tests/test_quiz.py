import io
import json

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document, QuizQuestion
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider


def _quiz_json(options=None, correct_index=1):
    return json.dumps(
        [
            {
                "question": "What is 2 + 2?",
                "options": options or ["3", "4", "5", "6"],
                "correct_answer_index": correct_index,
            }
        ]
    )


class FakeQuizProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        return _quiz_json()


class OutOfRangeAnswerProvider(AIProvider):
    """Simulates the model picking a correct_answer_index that doesn't
    actually point at one of the options — a real failure mode distinct
    from 'not valid JSON at all'."""

    async def generate_text(self, prompt: str) -> str:
        return _quiz_json(correct_index=99)


class FailingAIProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


class CountingAIProvider(AIProvider):
    """Records how many times it was actually asked to generate text,
    so a test can assert the AI was never called for a textless
    document."""

    def __init__(self):
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return _quiz_json()


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_ready_document(client: TestClient) -> str:
    pdf_bytes = _make_test_pdf("Some content to quiz on.")
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


def _seed_quiz_question(document_id: str, position: int = 0) -> None:
    """Inserts a QuizQuestion row directly, bypassing generation — used
    to simulate one that was already persisted (e.g. generated before
    this guard existed)."""
    db = SessionLocal()
    try:
        db.add(
            QuizQuestion(
                document_id=document_id,
                question="Stale question about nothing?",
                options=["A", "B", "C", "D"],
                correct_answer_index=0,
                position=position,
            )
        )
        db.commit()
    finally:
        db.close()


def test_create_quiz_returns_parsed_questions():
    app.dependency_overrides[get_ai_provider] = lambda: FakeQuizProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 201
    body = response.json()
    assert len(body) == 1
    assert body[0]["options"] == ["3", "4", "5", "6"]
    assert body[0]["correct_answer_index"] == 1

    app.dependency_overrides.clear()


def test_create_quiz_is_cached_on_second_call():
    app.dependency_overrides[get_ai_provider] = lambda: FakeQuizProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    first = client.post(f"/api/v1/documents/{document_id}/quiz")
    second = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert [q["id"] for q in first.json()] == [q["id"] for q in second.json()]

    app.dependency_overrides.clear()


def test_create_quiz_returns_502_for_out_of_range_answer_index():
    app.dependency_overrides[get_ai_provider] = lambda: OutOfRangeAnswerProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_quiz_returns_502_when_provider_fails():
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_quiz_404_for_missing_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeQuizProvider()
    client = TestClient(app)

    response = client.post("/api/v1/documents/does-not-exist/quiz")

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_get_quiz_returns_empty_list_before_generation():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.get(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 200
    assert response.json() == []


def test_get_quiz_404_for_missing_document():
    client = TestClient(app)

    response = client.get("/api/v1/documents/does-not-exist/quiz")

    assert response.status_code == 404


def test_create_quiz_422_for_document_with_no_readable_text():
    """
    A document can reach "ready" (extraction completed without
    raising) while extracted_text is still blank — e.g. a scanned or
    image-only file OCR found no readable characters in. Generating a
    quiz for it should say so clearly rather than sending an empty
    document to the AI, which would otherwise invent quiz questions
    about a topic that was never actually in the document.
    """
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_create_quiz_422_for_whitespace_only_text():
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("   \n\t  ")

    response = client.post(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_get_quiz_422_for_document_with_no_readable_text():
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.get(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()


def test_get_quiz_422_even_with_stale_cached_questions():
    """
    Quiz questions that already exist for a document (e.g. generated
    before this guard existed) must not be served back once the
    document itself has no readable text — GET must refuse the same
    way POST does, not quietly return the stale questions as if they
    were valid, document-derived content.
    """
    document_id = _seed_ready_document_with_text("")
    _seed_quiz_question(document_id)

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{document_id}/quiz")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
