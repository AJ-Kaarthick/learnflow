import io
import json

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.provider_factory import get_ai_provider

VALID_TREE = {
    "title": "Photosynthesis",
    "children": [
        {"title": "Light Reactions", "children": [{"title": "Chlorophyll", "children": []}]},
        {"title": "Calvin Cycle", "children": []},
    ],
}


class FakeMindMapProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        return json.dumps(VALID_TREE)


class FencedMindMapProvider(AIProvider):
    """Simulates a model wrapping the JSON object in markdown fences."""

    async def generate_text(self, prompt: str) -> str:
        return f"```json\n{json.dumps(VALID_TREE)}\n```"


class MissingTitleProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        return json.dumps({"children": [{"title": "Orphan node", "children": []}]})


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
    pdf_bytes = _make_test_pdf("Some content to map out.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def test_create_mindmap_returns_parsed_tree():
    app.dependency_overrides[get_ai_provider] = lambda: FakeMindMapProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 201
    body = response.json()
    assert body["structure"]["title"] == "Photosynthesis"
    assert len(body["structure"]["children"]) == 2

    app.dependency_overrides.clear()


def test_create_mindmap_strips_markdown_code_fences():
    app.dependency_overrides[get_ai_provider] = lambda: FencedMindMapProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 201
    assert response.json()["structure"]["title"] == "Photosynthesis"

    app.dependency_overrides.clear()


def test_create_mindmap_is_cached_on_second_call():
    app.dependency_overrides[get_ai_provider] = lambda: FakeMindMapProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    first = client.post(f"/api/v1/documents/{document_id}/mindmap")
    second = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert first.json()["id"] == second.json()["id"]

    app.dependency_overrides.clear()


def test_create_mindmap_returns_502_for_invalid_tree_shape():
    app.dependency_overrides[get_ai_provider] = lambda: MissingTitleProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_mindmap_returns_502_when_provider_fails():
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_mindmap_404_for_missing_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeMindMapProvider()
    client = TestClient(app)

    response = client.post("/api/v1/documents/does-not-exist/mindmap")

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_get_mindmap_404_before_generation():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.get(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 404
