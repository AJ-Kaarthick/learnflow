import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Document, RevisionAttempt, RevisionQuestion, RevisionSession
from app.main import app
from app.schemas.learn import (
    MAX_LEARN_DOCUMENT_IDS,
    LearnOutlineRequest,
    LearnTopicRequest,
)
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_document(self, text: str) -> list[float]:
        return [1.0, 0.0]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeAIProvider(AIProvider):
    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.call_count = 0
        self.custom_outline_response: str | None = None
        self.custom_topic_response: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        self.call_count += 1

        if "curriculum" in prompt.lower() or "study outline" in prompt.lower():
            if self.custom_outline_response is not None:
                return self.custom_outline_response
            return json.dumps(
                {
                    "title": "Introduction to Operating Systems",
                    "description": "Comprehensive course curriculum on OS and Concurrency.",
                    "learning_objectives": ["Understand processes", "Master synchronization"],
                    "topics": [
                        {
                            "id": "topic-1",
                            "title": "Processes & Threads",
                            "description": "Basics of execution units and concurrency.",
                            "learning_objectives": ["Distinguish processes and threads"],
                            "subtopics": [
                                {
                                    "id": "topic-1-1",
                                    "title": "Thread Scheduling",
                                    "summary": "Round-robin and priority scheduling algorithms.",
                                }
                            ],
                        },
                        {
                            "id": "topic-2",
                            "title": "Deadlocks & Semaphores",
                            "description": "Concurrency synchronization and mutual exclusion.",
                            "learning_objectives": ["Analyze resource deadlock conditions"],
                            "subtopics": [
                                {
                                    "id": "topic-2-1",
                                    "title": "Banker's Algorithm",
                                    "summary": "Deadlock avoidance mechanism.",
                                }
                            ],
                        },
                    ],
                }
            )

        if self.custom_topic_response is not None:
            return self.custom_topic_response

        return json.dumps(
            {
                "explanation": "Threads are lightweight units of execution within a process that share memory.",
                "key_terms": [
                    {
                        "term": "Thread",
                        "definition": "Smallest sequence of programmed instructions managed by a scheduler.",
                    }
                ],
                "key_takeaways": [
                    "Threads share the same address space.",
                    "Synchronization is required to prevent race conditions.",
                ],
            }
        )


class FailingAIProvider(AIProvider):
    async def generate_text(self, prompt: str) -> str:
        raise AIProviderError("Simulated upstream provider outage.")


def _seed_document(
    filename: str = "test.pdf",
    text: str = "Process management and synchronization in modern computing. " * 30,
    status: str = "ready",
    owner_type: str | None = None,
    owner_id: str | None = None,
) -> str:
    db = SessionLocal()
    try:
        doc = Document(
            original_filename=filename,
            stored_filename=filename,
            status=status,
            extracted_text=text,
            owner_type=owner_type,
            owner_id=owner_id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


# ---------------------------------------------------------------------
# 1. Request / Response Schema Validation
# ---------------------------------------------------------------------

def test_learn_schemas_validation():
    # Valid outline request
    req = LearnOutlineRequest(document_ids=["doc-1", "doc-2"], depth="overview")
    assert req.document_ids == ["doc-1", "doc-2"]
    assert req.depth == "overview"

    # Deduplication
    req_dup = LearnOutlineRequest(document_ids=["doc-1", "doc-2", "doc-1"])
    assert req_dup.document_ids == ["doc-1", "doc-2"]

    # More than 10 documents rejected
    with pytest.raises(Exception):
        LearnOutlineRequest(document_ids=[f"doc-{i}" for i in range(11)])

    # Empty document_ids rejected
    with pytest.raises(Exception):
        LearnOutlineRequest(document_ids=[])

    # Valid topic request
    topic_req = LearnTopicRequest(
        document_ids=["doc-1"],
        topic_id="topic-1",
        topic_title="Threads",
        action="simplify",
        depth="standard",
    )
    assert topic_req.topic_title == "Threads"
    assert topic_req.action == "simplify"

    # Invalid action rejected
    with pytest.raises(Exception):
        LearnTopicRequest(
            document_ids=["doc-1"],
            topic_id="topic-1",
            topic_title="Threads",
            action="summarize",  # not allowed
        )

    # Invalid depth rejected
    with pytest.raises(Exception):
        LearnTopicRequest(
            document_ids=["doc-1"],
            topic_id="topic-1",
            topic_title="Threads",
            depth="extreme",  # not allowed
        )


# ---------------------------------------------------------------------
# 2. Single-Document Outline
# ---------------------------------------------------------------------

def test_single_document_outline():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(filename="os_basics.pdf")

    resp_outline = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id], "depth": "standard"},
    )
    assert resp_outline.status_code == 200
    outline_data = resp_outline.json()
    assert outline_data["document_ids"] == [doc_id]
    assert len(outline_data["topics"]) == 2
    assert outline_data["topics"][0]["id"] == "topic-1"
    assert outline_data["grounding_metadata"]["total_topics"] == 2
    assert len(outline_data["grounding_metadata"]["contributing_documents"]) == 1

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 3. Single-Document Topic
# ---------------------------------------------------------------------

def test_single_document_topic():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(filename="os_basics.pdf")

    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "topic-1",
            "topic_title": "Processes & Threads",
            "depth": "standard",
        },
    )
    assert resp_topic.status_code == 200
    topic_data = resp_topic.json()
    assert topic_data["topic_id"] == "topic-1"
    assert topic_data["topic_title"] == "Processes & Threads"
    assert "Threads are lightweight" in topic_data["explanation"]
    assert len(topic_data["key_terms"]) == 1
    assert len(topic_data["key_takeaways"]) == 2
    assert topic_data["grounding_metadata"]["grounded"] is True

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 4. Multi-Document Outline
# ---------------------------------------------------------------------

def test_multi_document_outline():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc1 = _seed_document(filename="doc1.pdf", text="Operating systems fundamentals. " * 20)
    doc2 = _seed_document(filename="doc2.pdf", text="Database management concurrency. " * 20)

    resp_outline = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc1, doc2], "depth": "in-depth"},
    )
    assert resp_outline.status_code == 200
    outline_data = resp_outline.json()
    assert outline_data["document_ids"] == [doc1, doc2]
    assert len(outline_data["grounding_metadata"]["contributing_documents"]) == 2

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 5. Multi-Document Topic
# ---------------------------------------------------------------------

def test_multi_document_topic():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc1 = _seed_document(filename="doc1.pdf", text="Operating systems fundamentals. " * 20)
    doc2 = _seed_document(filename="doc2.pdf", text="Database management concurrency. " * 20)

    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc1, doc2],
            "topic_id": "topic-2",
            "topic_title": "Deadlocks & Semaphores",
            "depth": "in-depth",
        },
    )
    assert resp_topic.status_code == 200
    topic_data = resp_topic.json()
    assert topic_data["topic_id"] == "topic-2"
    assert topic_data["depth"] == "in-depth"
    assert topic_data["grounding_metadata"]["grounded"] is True

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 4. Maximum 10-Document Selection
# ---------------------------------------------------------------------

def test_max_ten_documents_accepted():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_ids = [_seed_document(filename=f"doc_{i}.pdf") for i in range(10)]

    response = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": doc_ids},
    )
    assert response.status_code == 200
    assert len(response.json()["grounding_metadata"]["contributing_documents"]) == 10

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 5. More than 10 Documents Rejected
# ---------------------------------------------------------------------

def test_more_than_ten_documents_rejected():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_ids = [f"fake-doc-{i}" for i in range(MAX_LEARN_DOCUMENT_IDS + 1)]

    # Outline
    resp_outline = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": doc_ids},
    )
    assert resp_outline.status_code == 422

    # Topic
    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={"document_ids": doc_ids, "topic_id": "top-1", "topic_title": "Title"},
    )
    assert resp_topic.status_code == 422

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 6. Ownership / Isolation Enforcement
# ---------------------------------------------------------------------

def test_ownership_isolation_enforced():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    # Document owned specifically by user_owner_99
    doc_id = _seed_document(
        filename="private.pdf",
        owner_type="user",
        owner_id="user_owner_99",
    )

    # Anonymous guest request should receive 404
    resp_outline = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id]},
    )
    assert resp_outline.status_code == 404
    assert f"Document not found: {doc_id}" in resp_outline.json()["detail"]

    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={"document_ids": [doc_id], "topic_id": "top-1", "topic_title": "Title"},
    )
    assert resp_topic.status_code == 404

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 7. Guest Identity Behavior
# ---------------------------------------------------------------------

def test_guest_identity_behavior():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    # Legacy / unowned document is accessible to guests
    doc_id = _seed_document(filename="guest_accessible.pdf")

    resp = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id]},
    )
    assert resp.status_code == 200
    assert "learnflow_session" in resp.cookies or "Set-Cookie" in resp.headers

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 8. Guest AI-Generation Quota Enforcement & Record Only on Success
# ---------------------------------------------------------------------

def test_guest_ai_generation_quota_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "guest_max_ai_generations", 2)

    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(filename="quota_test.pdf")

    # 1st call: succeeds
    resp1 = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp1.status_code == 200

    # 2nd call: succeeds
    resp2 = client.post(
        "/api/v1/study/learn/topic",
        json={"document_ids": [doc_id], "topic_id": "t1", "topic_title": "Threads"},
    )
    assert resp2.status_code == 200

    # 3rd call: hits guest quota limit
    resp3 = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp3.status_code == 403
    assert resp3.json()["detail"]["code"] == "guest_limit_reached"
    assert resp3.json()["detail"]["limit_type"] == "ai_generation"

    # Verify failed call does NOT consume quota if failing before success
    # Reset limit to 1
    monkeypatch.setattr(settings, "guest_max_ai_generations", 1)
    failing_ai = FailingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: failing_ai
    fresh_client = TestClient(app)

    # 1st call fails due to AI outage -> returns 502
    resp_failed = fresh_client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp_failed.status_code == 502

    # Swap back to working AI -> quota should NOT have been decremented by the failure
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    resp_success = fresh_client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp_success.status_code == 200

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 9. READY / Readable Document Acceptance
# ---------------------------------------------------------------------

def test_ready_readable_document_acceptance():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(status="ready", text="Valid extractable text for reading.")
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 200

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 12. PROCESSING Rejection (Single-Doc)
# ---------------------------------------------------------------------

def test_processing_document_rejected():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(status="processing")
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 400
    assert "status: processing" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 13. UPLOADING Rejection (Single-Doc)
# ---------------------------------------------------------------------

def test_uploading_document_rejected():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(status="uploading")
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 400
    assert "status: uploading" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 14. FAILED Rejection (Single-Doc)
# ---------------------------------------------------------------------

def test_failed_document_rejected():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(status="failed")
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 400
    assert "status: failed" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 11. Empty Document Rejection (Single-Doc)
# ---------------------------------------------------------------------

def test_empty_document_rejected_single_doc():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(status="ready", text="")
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 422
    assert "No readable text" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 12. Mixed Readable / Unreadable Documents (Multi-Doc)
# ---------------------------------------------------------------------

def test_mixed_readable_unreadable_documents_multi_doc():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_ready = _seed_document(filename="good.pdf", status="ready", text="Good text content.")
    doc_unready = _seed_document(filename="processing.pdf", status="processing", text="")

    resp = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_ready, doc_unready]},
    )
    assert resp.status_code == 200
    body = resp.json()
    prov = body["grounding_metadata"]
    assert len(prov["contributing_documents"]) == 1
    assert prov["contributing_documents"][0]["id"] == doc_ready
    assert len(prov["excluded_documents"]) == 1
    assert prov["excluded_documents"][0]["id"] == doc_unready
    assert prov["excluded_documents"][0]["reason"] == "status_processing"

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 13. Zero-Readable-Document Rejection (Multi-Doc)
# ---------------------------------------------------------------------

def test_zero_readable_documents_rejected_multi_doc():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc1 = _seed_document(status="processing", text="")
    doc2 = _seed_document(status="failed", text="")

    resp = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc1, doc2]},
    )
    assert resp.status_code == 400
    assert "No readable documents available" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 14. RAG Retrieval is Actually Used for Topic Generation
# ---------------------------------------------------------------------

def test_rag_retrieval_used_for_topic_generation():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(
        filename="kernel_threads.pdf",
        text="Kernel threads are scheduled directly by the OS kernel without runtime overhead. " * 30,
    )

    resp = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "topic-1",
            "topic_title": "Kernel Threads",
        },
    )
    assert resp.status_code == 200
    # Assert that the prompt sent to the model actually contained the source excerpt from RAG
    assert fake_ai.last_prompt is not None
    assert "Source Excerpts:" in fake_ai.last_prompt
    assert "kernel_threads.pdf" in fake_ai.last_prompt

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 15. Source Citation / Grounding Metadata
# ---------------------------------------------------------------------

def test_source_citation_and_grounding_metadata():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document(filename="citations.pdf", text="Important factual excerpt for citation. " * 30)

    resp = client.post(
        "/api/v1/study/learn/topic",
        json={"document_ids": [doc_id], "topic_id": "t1", "topic_title": "Citations"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) > 0
    citation = data["sources"][0]
    assert citation["document_id"] == doc_id
    assert citation["document_name"] == "citations.pdf"
    assert "content" in citation
    assert "score" in citation
    assert data["grounding_metadata"]["grounded"] is True
    assert data["grounding_metadata"]["retrieved_chunks_count"] > 0

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 16. Structured JSON Parsing / Validation
# ---------------------------------------------------------------------

def test_structured_json_parsing_and_validation():
    fake_ai = FakeAIProvider()
    # Provide response wrapped in markdown code fence
    fake_ai.custom_outline_response = (
        "```json\n"
        + json.dumps(
            {
                "title": "Clean Curriculum",
                "description": "Clean description",
                "learning_objectives": ["Goal 1"],
                "topics": [
                    {
                        "id": "t1",
                        "title": "T1",
                        "description": "D1",
                        "learning_objectives": ["L1"],
                        "subtopics": [{"id": "s1", "title": "S1", "summary": "Sum"}],
                    }
                ],
            }
        )
        + "\n```"
    )

    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Clean Curriculum"
    assert data["topics"][0]["id"] == "t1"
    assert data["topics"][0]["subtopics"][0]["title"] == "S1"

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 17. Malformed AI Output Handling (502, Never Crashes with 500)
# ---------------------------------------------------------------------

def test_malformed_ai_output_handled_gracefully():
    fake_ai = FakeAIProvider()
    fake_ai.custom_outline_response = "Not valid JSON at all!"
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()
    resp = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp.status_code == 502
    assert "JSON" in resp.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 18. Simplify Action
# ---------------------------------------------------------------------

def test_simplify_action():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()
    resp = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "top-1",
            "topic_title": "Virtual Memory",
            "action": "simplify",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "simplify"
    assert fake_ai.last_prompt is not None
    assert "simple, intuitive terms" in fake_ai.last_prompt

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 19. Elaborate Action
# ---------------------------------------------------------------------

def test_elaborate_action():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()
    resp = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "top-1",
            "topic_title": "Virtual Memory",
            "action": "elaborate",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "elaborate"
    assert fake_ai.last_prompt is not None
    assert "deep, detailed, and comprehensive" in fake_ai.last_prompt

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 20. Example Action
# ---------------------------------------------------------------------

def test_example_action():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()
    resp = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "top-1",
            "topic_title": "Virtual Memory",
            "action": "example",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "example"
    assert fake_ai.last_prompt is not None
    assert "concrete, realistic example" in fake_ai.last_prompt

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 21. Depth Control Validation
# ---------------------------------------------------------------------

def test_depth_control_validation_and_instructions():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()

    # Overview depth
    resp_overview = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id], "depth": "overview"},
    )
    assert resp_overview.status_code == 200
    assert "high-level overview" in fake_ai.last_prompt

    # In-depth depth
    resp_indepth = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id], "depth": "in-depth"},
    )
    assert resp_indepth.status_code == 200
    assert "extensive, rigorous" in fake_ai.last_prompt

    # Invalid depth rejected
    resp_invalid = client.post(
        "/api/v1/study/learn/outline",
        json={"document_ids": [doc_id], "depth": "unsupported"},
    )
    assert resp_invalid.status_code == 422

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 22. AI Provider Failure Handling
# ---------------------------------------------------------------------

def test_ai_provider_failure_returns_502():
    failing_ai = FailingAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: failing_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    doc_id = _seed_document()

    resp_outline = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp_outline.status_code == 502
    assert "outage" in resp_outline.json()["detail"]

    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={"document_ids": [doc_id], "topic_id": "top-1", "topic_title": "Title"},
    )
    assert resp_topic.status_code == 502
    assert "outage" in resp_topic.json()["detail"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------
# 23. Revision Isolation — Learn Must Not Touch Revision Data
# ---------------------------------------------------------------------

def test_revision_isolation_learn_does_not_touch_revision_tables():
    fake_ai = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    db = SessionLocal()
    try:
        # Seed a persistent Revision session and question
        rev_session = RevisionSession(
            title="Pre-existing Revision Session",
            owner_type="guest",
            owner_id="guest-rev-test",
        )
        db.add(rev_session)
        db.commit()
        db.refresh(rev_session)

        question = RevisionQuestion(
            session_id=rev_session.id,
            position=0,
            question_type="multiple_choice",
            question_text="What is virtual memory?",
            correct_answer="An abstraction of main memory.",
        )
        db.add(question)
        db.commit()

        initial_session_count = db.query(RevisionSession).count()
        initial_question_count = db.query(RevisionQuestion).count()
        initial_attempt_count = db.query(RevisionAttempt).count()
    finally:
        db.close()

    doc_id = _seed_document(filename="isolation.pdf")

    # Run outline generation
    resp_outline = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc_id]})
    assert resp_outline.status_code == 200

    # Run topic generation with action
    resp_topic = client.post(
        "/api/v1/study/learn/topic",
        json={
            "document_ids": [doc_id],
            "topic_id": "top-1",
            "topic_title": "Memory",
            "action": "simplify",
        },
    )
    assert resp_topic.status_code == 200

    # Verify Revision database state is 100% untouched
    db_verify = SessionLocal()
    try:
        final_session_count = db_verify.query(RevisionSession).count()
        final_question_count = db_verify.query(RevisionQuestion).count()
        final_attempt_count = db_verify.query(RevisionAttempt).count()

        assert final_session_count == initial_session_count
        assert final_question_count == initial_question_count
        assert final_attempt_count == initial_attempt_count
    finally:
        db_verify.close()

    app.dependency_overrides.clear()
