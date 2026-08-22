import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document, Summary
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


class CountingAIProvider(AIProvider):
    """Records how many times it was actually asked to generate text,
    so a test can assert the AI was never called at all — not just
    that its (possibly fabricated) output didn't make it into the
    response."""

    def __init__(self):
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        return "This should never be generated for a textless document."


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


def _seed_ready_document_with_text(extracted_text: str) -> str:
    """
    Inserts a "ready" Document row directly via the DB session, with
    whatever `extracted_text` the test needs — same pattern
    test_rag.py's _seed_ready_document_with_text uses: a document
    whose extraction succeeded but found nothing (or only whitespace)
    isn't something the upload endpoint can produce on demand with a
    real PDF, so this bypasses the extraction pipeline entirely rather
    than depending on a specific extractor's blank-input behavior.
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


def _seed_summary(document_id: str, content: str) -> None:
    """
    Inserts a Summary row directly, bypassing generation entirely —
    used to simulate a summary that was already persisted (e.g.
    generated before this guard existed) so tests can confirm GET
    won't serve it back once the document has no readable text.
    """
    db = SessionLocal()
    try:
        db.add(Summary(document_id=document_id, content=content))
        db.commit()
    finally:
        db.close()


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


def test_create_summary_422_for_document_with_no_readable_text():
    """
    A document can reach "ready" (extraction completed without
    raising) while extracted_text is still blank — e.g. a scanned or
    image-only file OCR found no readable characters in. Generating a
    summary for it should say so clearly rather than sending an empty
    document to the AI and getting back a plausible-looking summary of
    nothing.
    """
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.post(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    # The whole point: no AI request should ever have gone out for a
    # document with nothing to summarize.
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_create_summary_422_for_whitespace_only_text():
    provider = CountingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("   \n\t  ")

    response = client.post(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
    assert provider.call_count == 0

    app.dependency_overrides.clear()


def test_get_summary_422_for_document_with_no_readable_text():
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.get(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()


def test_get_summary_422_even_with_a_stale_cached_summary():
    """
    Guards against exactly the "existing cached/persisted content"
    risk this fix has to account for: a Summary row that already
    exists for a document (e.g. generated before this guard existed)
    must not be served back once the document itself has no readable
    text — GET must refuse the same way POST does, not quietly return
    the stale row as if it were valid.
    """
    document_id = _seed_ready_document_with_text("")
    _seed_summary(document_id, "A stale summary from before the fix.")

    client = TestClient(app)
    response = client.get(f"/api/v1/documents/{document_id}/summary")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()
