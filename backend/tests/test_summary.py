import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider


class FakeAIProvider(AIProvider):
    """Stands in for a real provider in tests — instant, free, and
    deterministic. This is only possible because routes depend on
    AIProvider through get_ai_provider(), never on GeminiProvider directly."""

    async def generate_text(self, prompt: str) -> str:
        return "This is a fake summary for testing."


class FailingAIProvider(AIProvider):
    """Simulates the AI service being down, to test our error handling."""

    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_ready_document(client: TestClient) -> str:
    pdf_bytes = _make_test_pdf("Some content to summarize.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def test_create_summary_returns_generated_content():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)

    document_id = _upload_ready_document(client)
    response = client.post(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 201
    body = response.json()
    assert body["content"] == "This is a fake summary for testing."
    assert body["document_id"] == document_id

    app.dependency_overrides.clear()


def test_create_summary_is_cached_on_second_call():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    first = client.post(f"/api/v1/documents/{document_id}/summary")
    second = client.post(f"/api/v1/documents/{document_id}/summary")

    assert first.json()["id"] == second.json()["id"]

    app.dependency_overrides.clear()


def test_create_summary_returns_502_when_provider_fails():
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_summary_404_for_missing_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)

    response = client.post("/api/v1/documents/does-not-exist/summary")

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_get_summary_404_before_generation():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.get(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 404
