import io
import json

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

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
