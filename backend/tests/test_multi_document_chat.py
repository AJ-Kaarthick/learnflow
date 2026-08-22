import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import NO_CONTEXT_ANSWER
from app.schemas.chat import MAX_DOCUMENT_IDS

# Each document is entirely about one topic, so a query that's purely
# about one topic scores the *other* document's chunks at exactly 0.0
# (orthogonal vectors) — the sharpest possible test of whether
# per-document top_k still includes a document that scores far lower
# than the other, which is the entire point of multi-document
# retrieval (see retrieval_service.retrieve_relevant_chunks).
CATS_TEXT = "The cat sat on the mat. " * 60
DOGS_TEXT = "The dog ran in the yard. " * 60


class KeywordEmbeddingProvider(EmbeddingProvider):
    """
    Returns a 2D vector based on whether a text is cat-dominant or
    dog-dominant — the same technique test_rag.py uses, needed here
    (rather than test_chat.py's simpler constant-vector fake) because
    these tests need to prove a document that scores *lower* still
    gets represented, not just that retrieval returns something.
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


class FailingAIProvider(AIProvider):
    """Simulates the AI service being down."""

    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated provider failure.")


class FakeAIProvider(AIProvider):
    """Returns a fixed answer and records the prompt it was called with."""

    def __init__(self, answer: str = "Cats and dogs are both discussed in the excerpts.") -> None:
        self._answer = answer
        self.last_prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._answer


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_and_index_document(client: TestClient, filename: str, text: str) -> str:
    pdf_bytes = _make_test_pdf(text)
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]
    client.post(f"/api/v1/documents/{document_id}/index")
    return document_id


def _upload_cats_and_dogs(client: TestClient) -> tuple[str, str]:
    cats_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)
    dogs_id = _upload_and_index_document(client, "dogs.pdf", DOGS_TEXT)
    return cats_id, dogs_id


def _seed_ready_document_with_text(filename: str, extracted_text: str) -> str:
    """
    Same pattern as test_chat.py's and test_rag.py's helper of the
    same name — a "ready" document whose extracted_text the upload
    endpoint can't produce on demand (real extraction/OCR would need
    an actual blank image on disk). Takes an explicit filename, unlike
    those single-document versions, so a test can assert on which of
    several seeded documents a multi-document response/error is about.
    """
    db = SessionLocal()
    try:
        document = Document(
            original_filename=filename,
            stored_filename=filename,
            status="ready",
            extracted_text=extracted_text,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id
    finally:
        db.close()


def test_multi_document_chat_represents_every_selected_document():
    """
    The core new retrieval behavior: even though the query is purely
    about cats (so every dog chunk scores 0.0 — completely unrelated
    by cosine similarity), the dog document still contributes sources,
    because retrieve_relevant_chunks guarantees each selected document
    up to top_k chunks rather than pooling and taking one global top_k.
    """
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    source_document_ids = {source["document_id"] for source in body["sources"]}
    assert source_document_ids == {cats_id, dogs_id}

    app.dependency_overrides.clear()


def test_multi_document_chat_sources_include_document_information():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "Compare cats and dogs"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_ids"] == [cats_id, dogs_id]
    assert body["question"] == "Compare cats and dogs"
    for source in body["sources"]:
        assert set(source.keys()) == {
            "chunk_id",
            "chunk_index",
            "content",
            "score",
            "document_id",
            "document_name",
        }
        assert source["document_name"] in ("cats.pdf", "dogs.pdf")

    app.dependency_overrides.clear()


def test_multi_document_chat_labels_excerpts_by_document_in_prompt():
    """
    Confirms build_chat_prompt actually names each source document in
    the prompt sent to the model — without this, the model has no way
    to know which excerpt belongs to which document when asked to
    compare them.
    """
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "Compare cats and dogs"},
    )

    prompt = fake_ai_provider.last_prompt
    assert prompt is not None
    assert "cats.pdf" in prompt
    assert "dogs.pdf" in prompt
    # Grounding instructions still present, unchanged in substance.
    assert "ONLY" in prompt
    assert NO_CONTEXT_ANSWER in prompt

    app.dependency_overrides.clear()


def test_multi_document_chat_prompt_prefers_filenames_over_generic_labels():
    """
    The prompt must steer the model toward calling a document by its
    filename (already available via the excerpt labels) rather than a
    generic, unpolished label like "Document 1" or "Document 2" when
    it needs to refer to one — without weakening any grounding
    instruction already covered by
    test_multi_document_chat_labels_excerpts_by_document_in_prompt.
    """
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "Compare cats and dogs"},
    )

    prompt = fake_ai_provider.last_prompt
    assert prompt is not None
    assert "filename" in prompt.lower()
    assert '"Document 1"' in prompt

    app.dependency_overrides.clear()


def test_multi_document_chat_includes_conversation_history():
    fake_ai_provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    client.post(
        "/api/v1/documents/chat",
        json={
            "document_ids": [cats_id, dogs_id],
            "question": "What about the other one?",
            "history": [
                {"role": "user", "content": "Tell me about cats."},
                {"role": "assistant", "content": "Cats sat on mats."},
            ],
        },
    )

    prompt = fake_ai_provider.last_prompt
    assert "Tell me about cats." in prompt
    assert "Cats sat on mats." in prompt
    assert "NOT a source of facts" in prompt

    app.dependency_overrides.clear()


def test_multi_document_chat_hallucination_prevention_still_works():
    fake_ai_provider = FakeAIProvider(answer=NO_CONTEXT_ANSWER)
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "What is the capital of France?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NO_CONTEXT_ANSWER
    assert body["grounded"] is True

    app.dependency_overrides.clear()


def test_multi_document_chat_404_for_missing_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, _dogs_id = _upload_cats_and_dogs(client)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, "does-not-exist"], "question": "Tell me about cats"},
    )

    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]

    app.dependency_overrides.clear()


def test_multi_document_chat_400_for_unindexed_document():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)

    # Uploaded but deliberately not indexed.
    pdf_bytes = _make_test_pdf(DOGS_TEXT)
    upload_response = client.post(
        "/api/v1/documents/upload", files={"file": ("dogs.pdf", pdf_bytes, "application/pdf")}
    )
    unindexed_dogs_id = upload_response.json()["id"]

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, unindexed_dogs_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_multi_document_chat_422_when_one_selected_document_has_no_readable_text():
    """
    V2.4 Milestone 1 UX polish (issue 2): the backend's per-document
    guard (routes_chat.py's _get_indexed_document) is intentionally
    unchanged by this milestone — the actual fix is client-side (see
    frontend/src/utils/documentReadiness.splitDocumentsByReadability
    and ChatPanel.jsx), which now filters an unreadable document out
    of document_ids before ever calling this endpoint, rather than
    discovering the problem from this 422 after the fact.

    This test locks in the backend contract that filtering depends on
    staying true: if a document with no readable text *is* included in
    document_ids anyway (a direct API caller, or a future regression
    that stops filtering client-side), the whole request still fails
    clearly and identifies that specific document — never silently
    drops it, and never answers from fewer documents than requested.
    """
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)
    blank_id = _seed_ready_document_with_text("Enso Wallpaper.jpg", "")

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, blank_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert blank_id in detail
    assert "no readable text" in detail.lower()

    app.dependency_overrides.clear()


def test_multi_document_chat_422_for_empty_document_ids():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)

    response = client.post(
        "/api/v1/documents/chat", json={"document_ids": [], "question": "Tell me about cats"}
    )

    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_multi_document_chat_422_for_too_many_document_ids():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)

    too_many_ids = [f"fake-id-{i}" for i in range(MAX_DOCUMENT_IDS + 1)]
    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": too_many_ids, "question": "Tell me about cats"},
    )

    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_multi_document_chat_deduplicates_repeated_document_ids():
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, cats_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 200
    assert response.json()["document_ids"] == [cats_id]

    app.dependency_overrides.clear()


def test_multi_document_chat_502_when_ai_provider_fails():
    app.dependency_overrides[get_ai_provider] = lambda: FailingAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id, dogs_id = _upload_cats_and_dogs(client)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id, dogs_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 502

    app.dependency_overrides.clear()


def test_multi_document_chat_works_with_a_single_document_id():
    """
    The multi-document endpoint isn't a separate implementation for
    "more than one" — a single-element list is a valid, ordinary call,
    same as retrieve_relevant_chunks and answer_question treat it.
    """
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    cats_id = _upload_and_index_document(client, "cats.pdf", CATS_TEXT)

    response = client.post(
        "/api/v1/documents/chat",
        json={"document_ids": [cats_id], "question": "Tell me about cats"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_ids"] == [cats_id]
    assert all(source["document_id"] == cats_id for source in body["sources"])

    app.dependency_overrides.clear()
