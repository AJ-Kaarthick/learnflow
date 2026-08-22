import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document
from app.main import app
from app.services.ai.base_provider import AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider

# Long enough to produce multiple chunks at the default 1000-character
# chunk size (see CHUNK_SIZE_CHARACTERS in chunking.py): the first
# ~1500 characters are cat sentences, the rest are dog sentences, so
# chunk 0 ends up cat-dominant and the last chunk ends up dog-dominant
# regardless of exactly where chunk boundaries fall.
CAT_AND_DOG_TEXT = ("The cat sat on the mat. " * 60) + ("The dog ran in the yard. " * 60)


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Stands in for a real embedding model the same way FakeAIProvider
    (test_summary.py) stands in for a real text-generation one — instant,
    free, deterministic, and only possible because routes depend on
    EmbeddingProvider through get_embedding_provider(), never on
    GeminiEmbeddingProvider directly.

    Returns a 2D vector based on whether a text is cat-dominant or
    dog-dominant, which is enough to make retrieval ranking assertable
    without needing a real embedding model's actual vector space.
    """

    async def embed_document(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        lowered = text.lower()
        cat_count = lowered.count("cat")
        dog_count = lowered.count("dog")
        if cat_count > dog_count:
            return [1.0, 0.0]
        if dog_count > cat_count:
            return [0.0, 1.0]
        return [0.5, 0.5]


class FailingEmbeddingProvider(EmbeddingProvider):
    """Simulates the embedding service being down, to test error handling."""

    async def embed_document(self, text: str) -> list[float]:
        raise AIProviderError("Simulated embedding provider failure.")

    async def embed_query(self, text: str) -> list[float]:
        raise AIProviderError("Simulated embedding provider failure.")


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_ready_document(client: TestClient, text: str = "Some content to index.") -> str:
    pdf_bytes = _make_test_pdf(text)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def _seed_ready_document_with_text(extracted_text: str) -> str:
    """
    Inserts a "ready" Document row directly via the DB session, with
    whatever `extracted_text` the test needs — same pattern
    test_document_manager.py's _seed_document_with_extension uses, for
    the same reason: this needs a document whose *content* (here,
    blank extracted text) the upload endpoint can't produce on demand,
    only whatever a real PDF/OCR run happens to extract. Skipping the
    real extraction pipeline also keeps this test fast and
    deterministic rather than depending on Tesseract actually being
    installed and returning "" for a blank page (see
    ocr/dependency_check.py) — this test is about the route's guard,
    not the extraction pipeline itself.
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


def test_create_index_chunks_and_embeds_document():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)

    response = client.post(f"/api/v1/documents/{document_id}/index")

    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] == document_id
    assert body["status"] == "indexed"
    assert body["chunk_count"] > 1  # CAT_AND_DOG_TEXT is longer than one chunk

    app.dependency_overrides.clear()


def test_create_index_is_idempotent_on_second_call():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)

    first = client.post(f"/api/v1/documents/{document_id}/index")
    second = client.post(f"/api/v1/documents/{document_id}/index")

    assert first.json()["chunk_count"] == second.json()["chunk_count"]
    assert first.json()["status"] == "indexed"
    assert second.json()["status"] == "already_indexed"

    app.dependency_overrides.clear()


def test_create_index_returns_502_when_embedding_provider_fails():
    app.dependency_overrides[get_embedding_provider] = lambda: FailingEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)

    response = client.post(f"/api/v1/documents/{document_id}/index")

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_create_index_404_for_missing_document():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post("/api/v1/documents/does-not-exist/index")

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_create_index_422_for_document_with_no_readable_text():
    """
    V2.4 Milestone 1 UX polish (issue 2): a document can reach "ready"
    (extraction completed without raising) while extracted_text is
    still blank — e.g. an image OCR found no readable characters in.
    Indexing it should say so clearly rather than silently "succeed"
    with zero chunks, which would let the frontend show the document
    as ready to chat with when nothing was actually indexed.
    """
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("")

    response = client.post(f"/api/v1/documents/{document_id}/index")

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_search_document_returns_most_similar_chunk_first():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)
    client.post(f"/api/v1/documents/{document_id}/index")

    cat_response = client.post(
        f"/api/v1/documents/{document_id}/search", json={"query": "Tell me about cats"}
    )
    dog_response = client.post(
        f"/api/v1/documents/{document_id}/search", json={"query": "Tell me about dogs"}
    )

    assert cat_response.status_code == 200
    cat_results = cat_response.json()["results"]
    assert cat_results  # at least one chunk came back
    assert "cat" in cat_results[0]["content"].lower()
    assert cat_results[0]["score"] >= cat_results[-1]["score"]  # sorted, best first

    dog_results = dog_response.json()["results"]
    assert "dog" in dog_results[0]["content"].lower()

    app.dependency_overrides.clear()


def test_search_document_respects_top_k():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)
    client.post(f"/api/v1/documents/{document_id}/index")

    response = client.post(
        f"/api/v1/documents/{document_id}/search", json={"query": "cats", "top_k": 1}
    )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1

    app.dependency_overrides.clear()


def test_search_document_400_before_indexing():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)

    response = client.post(
        f"/api/v1/documents/{document_id}/search", json={"query": "cats"}
    )

    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_search_document_422_for_blank_query():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)
    client.post(f"/api/v1/documents/{document_id}/index")

    response = client.post(f"/api/v1/documents/{document_id}/search", json={"query": "   "})

    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_search_document_422_for_document_with_no_readable_text():
    """Same guard as test_create_index_422_for_document_with_no_readable_text, for /search."""
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _seed_ready_document_with_text("   ")  # whitespace-only

    response = client.post(f"/api/v1/documents/{document_id}/search", json={"query": "anything"})

    assert response.status_code == 422
    assert "no readable text" in response.json()["detail"].lower()

    app.dependency_overrides.clear()


def test_search_document_404_for_missing_document():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post(
        "/api/v1/documents/does-not-exist/search", json={"query": "cats"}
    )

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_delete_document_removes_its_chunks():
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_ready_document(client, CAT_AND_DOG_TEXT)
    client.post(f"/api/v1/documents/{document_id}/index")

    delete_response = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_response.status_code == 204

    # The document is gone, so indexing it again should 404 rather than
    # silently operating on orphaned chunk rows.
    reindex_response = client.post(f"/api/v1/documents/{document_id}/index")
    assert reindex_response.status_code == 404

    app.dependency_overrides.clear()
