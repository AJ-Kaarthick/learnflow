import io
import json

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document, MindMap
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


class CountingAIProvider(AIProvider):
    """Records how many times it was actually asked to generate text,
    so a test can assert the AI was never called for a textless
    document."""

    def __init__(self):
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return json.dumps(VALID_TREE)


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


def _seed_mindmap(document_id: str, structure: dict) -> None:
    """Inserts a MindMap row directly, bypassing generation — used to
    simulate one that was already persisted (e.g. generated before
    this guard existed)."""
    db = SessionLocal()
    try:
        db.add(MindMap(document_id=document_id, structure=structure))
        db.commit()
    finally:
        db.close()


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


def test_create_mindmap_422_for_document_with_no_readable_text():
    """
    A document can reach "ready" (extraction completed without
    raising) while extracted_text is still blank — e.g. a scanned or
    image-only file OCR found no readable characters in. Generating a
    mind map for it should say so clearly rather than sending an empty
    document to the AI, which would otherwise invent a generic
    structure with no real relationship to the document.
    """
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_create_mindmap_422_for_whitespace_only_text():
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("   \n\t  ")

    response = client.post(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_get_mindmap_422_for_document_with_no_readable_text():
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.get(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()


def test_get_mindmap_422_even_with_a_stale_cached_mindmap():
    """
    A mind map that already exists for a document (e.g. generated
    before this guard existed) must not be served back once the
    document itself has no readable text — GET must refuse the same
    way POST does, not quietly return the stale structure as if it
    were valid, document-derived content.
    """
    document_id = _seed_ready_document_with_text("")
    _seed_mindmap(document_id, {"title": "Stale Root", "children": []})

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{document_id}/mindmap")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
