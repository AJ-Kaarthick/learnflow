import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document
from app.main import app
from app.services.ai.base_provider import AIProvider
from app.services.ai.provider_factory import get_ai_provider


class FakeAIProvider(AIProvider):
    """Stands in for a real provider — instant, free, deterministic."""

    async def generate_text(self, prompt: str) -> str:
        return "This is a fake summary for testing."


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_ready_document(client: TestClient, filename: str = "test.pdf") -> str:
    pdf_bytes = _make_test_pdf("Some content.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def test_list_documents_returns_uploaded_documents_newest_first():
    client = TestClient(app)
    first_id = _upload_ready_document(client, "first.pdf")
    second_id = _upload_ready_document(client, "second.pdf")

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    ids = [doc["id"] for doc in response.json()]
    assert second_id in ids and first_id in ids
    assert ids.index(second_id) < ids.index(first_id)


def test_rename_document_updates_filename():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Renamed.pdf"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Renamed.pdf"

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.json()["original_filename"] == "Renamed.pdf"


def test_rename_document_trims_whitespace():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "  Padded.pdf  "}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Padded.pdf"


def test_rename_document_rejects_blank_name():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(f"/api/v1/documents/{document_id}", json={"original_filename": "   "})

    assert response.status_code == 422


def test_rename_document_ignores_attempted_extension_change():
    """
    A user (or a direct API call) trying to rename "Workout.pdf" to
    "Workout.jpg" must not actually change the file's extension — the
    stored file is still a PDF, so the name has to keep saying so.
    """
    client = TestClient(app)
    document_id = _upload_ready_document(client, "Workout.pdf")

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Workout.jpg"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Workout.jpg.pdf"
    assert response.json()["original_filename"].endswith(".pdf")


def test_rename_document_accepts_base_name_without_extension():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Chapter 5 Notes"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Chapter 5 Notes.pdf"


def test_rename_document_preserves_internal_dots_in_base_name():
    """Multiple-dot names shouldn't get truncated at the first dot."""
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"original_filename": "Chapter 1.2 Notes.pdf"},
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Chapter 1.2 Notes.pdf"


def test_rename_document_is_case_insensitive_about_existing_extension():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Notes.PDF"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Notes.pdf"


def test_rename_document_rejects_name_that_is_only_the_extension():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.patch(f"/api/v1/documents/{document_id}", json={"original_filename": ".pdf"})

    assert response.status_code == 422


def test_rename_document_rejects_punctuation_only_names():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    for punctuation_only in ["...", "???", "__", "---", "!!!"]:
        response = client.patch(
            f"/api/v1/documents/{document_id}", json={"original_filename": punctuation_only}
        )
        assert response.status_code == 422, f"expected {punctuation_only!r} to be rejected"


def test_rename_document_accepts_names_with_punctuation_and_letters():
    """Punctuation mixed with real characters is fine — only *all*-punctuation names are rejected."""
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    for reasonable_name in ["DBMS (Unit 1)", "AI_Week_3", "C++ Basics"]:
        response = client.patch(
            f"/api/v1/documents/{document_id}", json={"original_filename": reasonable_name}
        )
        assert response.status_code == 200, f"expected {reasonable_name!r} to be accepted"
        assert response.json()["original_filename"] == f"{reasonable_name}.pdf"


def test_rename_document_rejects_duplicate_name():
    client = TestClient(app)
    _upload_ready_document(client, "DBMS.pdf")
    other_id = _upload_ready_document(client, "Other.pdf")

    response = client.patch(
        f"/api/v1/documents/{other_id}", json={"original_filename": "DBMS.pdf"}
    )

    assert response.status_code == 409


def test_rename_document_duplicate_check_is_case_and_whitespace_insensitive():
    client = TestClient(app)
    tag = uuid.uuid4().hex[:8]
    _upload_ready_document(client, f"{tag}-DBMS.pdf")
    other_id = _upload_ready_document(client, f"{tag}-Other.pdf")

    for attempted_name in [f"{tag}-dbms.pdf", f"  {tag}-DBMS.pdf  ", f"{tag}-DbMs"]:
        response = client.patch(
            f"/api/v1/documents/{other_id}", json={"original_filename": attempted_name}
        )
        assert response.status_code == 409, f"expected {attempted_name!r} to be rejected as a duplicate"


def test_rename_document_allows_renaming_to_its_own_current_name():
    """Renaming a document to the name it already has isn't a duplicate of itself."""
    client = TestClient(app)
    document_id = _upload_ready_document(client, "Same Name.pdf")

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Same Name.pdf"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Same Name.pdf"


def test_rename_document_duplicate_check_does_not_cross_extensions():
    """A .pdf named "Notes" and a .docx named "Notes" aren't duplicates of each other."""
    client = TestClient(app)
    tag = uuid.uuid4().hex[:8]
    pdf_id = _upload_ready_document(client, f"{tag}-Notes.pdf")
    docx_id = _seed_document_with_extension(f"{tag}-Something.docx")

    response = client.patch(
        f"/api/v1/documents/{docx_id}", json={"original_filename": f"{tag}-Notes"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == f"{tag}-Notes.docx"
    assert pdf_id != docx_id


def _seed_document_with_extension(filename: str) -> str:
    """
    Inserts a Document row directly via the DB session rather than
    through the upload endpoint. Upload currently only accepts PDFs
    (ALLOWED_CONTENT_TYPE in routes_documents.py), but the rename
    logic itself is extension-agnostic and needs to be provable for
    other file types before LearnFlow actually supports uploading
    them.
    """
    db = SessionLocal()
    try:
        document = Document(
            original_filename=filename,
            stored_filename=f"{uuid.uuid4()}{Path(filename).suffix}",
            status="ready",
            extracted_text="",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id
    finally:
        db.close()


def test_rename_preserves_non_pdf_extension():
    """
    The extension is derived from the document's own current name,

    not a hardcoded ".pdf" — a .docx document renamed today must still
    come back as .docx, proving this isn't PDF-specific.
    """
    client = TestClient(app)
    document_id = _seed_document_with_extension("Lecture Notes.docx")

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Renamed Notes"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "Renamed Notes.docx"


def test_rename_ignores_attempted_extension_change_for_non_pdf_document():
    client = TestClient(app)
    document_id = _seed_document_with_extension("Slides.pptx")

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Slides.docx"}
    )

    assert response.status_code == 200
    # The attempted ".docx" is treated as literal text in the base
    # name, not a real extension change — the file is still a .pptx.
    assert response.json()["original_filename"] == "Slides.docx.pptx"


def test_rename_document_with_no_extension_stays_extensionless():
    client = TestClient(app)
    document_id = _seed_document_with_extension("README")

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "READ_ME"}
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "READ_ME"


def test_open_and_delete_work_after_rename():
    """
    Renaming only touches the display name — the stored file (looked
    up via stored_filename, never original_filename) must still open
    and delete cleanly afterward.
    """
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    client.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "Renamed For Open And Delete Test"}
    )

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 200
    assert get_response.json()["original_filename"] == "Renamed For Open And Delete Test.pdf"
    assert get_response.json()["status"] == "ready"

    delete_response = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_response.status_code == 204


def test_rename_document_404_for_missing_document():
    client = TestClient(app)

    response = client.patch(
        "/api/v1/documents/does-not-exist", json={"original_filename": "New name.pdf"}
    )

    assert response.status_code == 404


def test_delete_document_removes_it():
    client = TestClient(app)
    document_id = _upload_ready_document(client)

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 204

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404


def test_delete_document_404_for_missing_document():
    client = TestClient(app)

    response = client.delete("/api/v1/documents/does-not-exist")

    assert response.status_code == 404


def test_delete_document_also_removes_cached_summary():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client)
    client.post(f"/api/v1/documents/{document_id}/summary")

    delete_response = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_response.status_code == 204

    # If the Summary row had been left orphaned instead of cleaned up,
    # this would return 200 with stale content instead of 404.
    summary_response = client.get(f"/api/v1/documents/{document_id}/summary")
    assert summary_response.status_code == 404

    app.dependency_overrides.clear()
