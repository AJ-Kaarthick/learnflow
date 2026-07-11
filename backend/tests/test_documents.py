import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app

client = TestClient(app)


def _make_test_pdf(text: str) -> bytes:
    """Generates a tiny real PDF in memory so tests don't depend on a
    fixture file sitting on disk somewhere."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def test_upload_document_extracts_text():
    pdf_bytes = _make_test_pdf("Hello LearnFlow")

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert "Hello LearnFlow" in body["text_preview"]
    assert body["character_count"] > 0


def test_upload_rejects_non_pdf_files():
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_rejects_empty_file():
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_get_document_returns_it_after_upload():
    pdf_bytes = _make_test_pdf("Retrieve me")
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]

    get_response = client.get(f"/api/v1/documents/{document_id}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == document_id


def test_get_document_returns_404_when_missing():
    response = client.get("/api/v1/documents/does-not-exist")

    assert response.status_code == 404
