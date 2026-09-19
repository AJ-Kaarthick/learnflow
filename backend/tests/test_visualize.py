import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Document, RevisionAttempt, RevisionQuestion, RevisionSession
from app.main import app
from app.schemas.visualize import (
    MAX_VISUALIZE_DOCUMENT_IDS,
    VisualizeGraphRequest,
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
        self.custom_graph_response: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.last_prompt = prompt
        self.call_count += 1
        return self._get_graph_response()

    async def generate_content(self, system_prompt: str, prompt: str) -> str:
        self.last_prompt = f"{system_prompt}\n\n{prompt}"
        self.call_count += 1
        return self._get_graph_response()

    def _get_graph_response(self) -> str:
        if self.custom_graph_response is not None:
            return self.custom_graph_response
        return json.dumps(
            {
                "title": "Operating Systems Concept Network",
                "summary": "Key architectural and algorithmic concepts across OS synchronization.",
                "nodes": [
                    {
                        "id": "concept_1",
                        "label": "Process Synchronization",
                        "summary": "Coordination of concurrent processes accessing shared resources.",
                        "category": "Core Theory",
                        "document_ids": ["doc-1"],
                        "importance": 2.0,
                    },
                    {
                        "id": "concept_2",
                        "label": "Mutex Locks",
                        "summary": "Binary semaphore enforcing mutual exclusion.",
                        "category": "Algorithm",
                        "document_ids": ["doc-1"],
                        "importance": 1.5,
                    },
                    {
                        "id": "concept_3",
                        "label": "Deadlock",
                        "summary": "State where processes are blocked waiting for resources held by each other.",
                        "category": "Failure State",
                        "document_ids": ["doc-1"],
                        "importance": 1.8,
                    },
                ],
                "edges": [
                    {
                        "id": "edge_2_1",
                        "source": "concept_2",
                        "target": "concept_1",
                        "label": "implements",
                    },
                    {
                        "id": "edge_1_3",
                        "source": "concept_1",
                        "target": "concept_3",
                        "label": "prevents",
                    },
                ],
            }
        )


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_ai():
    provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)


@pytest.fixture()
def fake_embed():
    provider = FakeEmbeddingProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.fixture()
def client(fake_ai, fake_embed):
    return TestClient(app)


def _signup_user(client: TestClient, email: str = "visualize_user@example.com") -> dict[str, Any]:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 201
    return resp.json()


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


def _create_ready_doc(
    content: str = "Process synchronization coordinates concurrent threads with mutexes to prevent deadlocks.",
    filename: str = "os_notes.pdf",
    user_id: str | None = None,
) -> dict[str, Any]:
    doc_id = _seed_document(
        filename=filename,
        text=content,
        status="ready",
        owner_type="user" if user_id else None,
        owner_id=user_id,
    )
    return {"id": doc_id, "original_filename": filename}


# ---------------------------------------------------------------------------
# Test 1: Schema validation
# ---------------------------------------------------------------------------
def test_visualize_schemas_validation():
    req = VisualizeGraphRequest(document_ids=["doc-1", "doc-2", "doc-1"], depth="overview")
    assert req.document_ids == ["doc-1", "doc-2"]
    assert req.depth == "overview"

    with pytest.raises(ValueError):
        VisualizeGraphRequest(document_ids=[])

    with pytest.raises(ValueError):
        VisualizeGraphRequest(document_ids=["doc-1"], depth="invalid-depth")  # type: ignore


# ---------------------------------------------------------------------------
# Test 2: More than 10 documents rejected with 422
# ---------------------------------------------------------------------------
def test_more_than_ten_documents_rejected(client: TestClient):
    _signup_user(client, "eleven_docs@example.com")
    doc_ids = [f"doc-{i}" for i in range(MAX_VISUALIZE_DOCUMENT_IDS + 1)]
    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": doc_ids, "depth": "standard"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test 3: Single document visualize graph happy path
# ---------------------------------------------------------------------------
def test_single_document_visualize_graph(client: TestClient):
    user = _signup_user(client, "single_vis@example.com")
    doc = _create_ready_doc(filename="concurrency.pdf", user_id=user["id"])

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "standard"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["title"] == "Operating Systems Concept Network"
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    assert data["nodes"][0]["label"] == "Process Synchronization"
    assert data["edges"][0]["label"] == "implements"
    assert data["grounding_metadata"]["total_nodes"] == 3
    assert data["grounding_metadata"]["total_edges"] == 2
    assert len(data["grounding_metadata"]["contributing_documents"]) == 1
    assert data["grounding_metadata"]["contributing_documents"][0]["id"] == doc["id"]


# ---------------------------------------------------------------------------
# Test 4: Multi-document visualize graph happy path
# ---------------------------------------------------------------------------
def test_multi_document_visualize_graph(client: TestClient, fake_ai: FakeAIProvider):
    user = _signup_user(client, "multi_vis@example.com")
    doc1 = _create_ready_doc("Raft consensus leader election", "raft.pdf", user_id=user["id"])
    doc2 = _create_ready_doc("Paxos multi-decree consensus protocol", "paxos.pdf", user_id=user["id"])

    fake_ai.custom_graph_response = json.dumps(
        {
            "title": "Distributed Consensus Concepts",
            "summary": "Comparison of Raft and Paxos.",
            "nodes": [
                {
                    "id": "node_1",
                    "label": "Consensus",
                    "summary": "Reaching agreement in distributed clusters.",
                    "category": "Theory",
                    "document_ids": [doc1["id"], doc2["id"]],
                    "importance": 2.5,
                },
                {
                    "id": "node_2",
                    "label": "Raft Leader",
                    "summary": "Designated leader per epoch.",
                    "category": "Algorithm",
                    "document_ids": [doc1["id"]],
                    "importance": 1.5,
                },
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "node_2",
                    "target": "node_1",
                    "label": "implements",
                }
            ],
        }
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc1["id"], doc2["id"]], "depth": "standard"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 2
    assert doc1["id"] in data["nodes"][0]["document_ids"]
    assert doc2["id"] in data["nodes"][0]["document_ids"]
    assert len(data["grounding_metadata"]["contributing_documents"]) == 2


# ---------------------------------------------------------------------------
# Test 5: Exactly 10 documents accepted
# ---------------------------------------------------------------------------
def test_max_ten_documents_accepted(client: TestClient):
    user = _signup_user(client, "ten_docs_vis@example.com")
    doc_ids = [
        _seed_document(
            filename=f"doc_{i}.pdf",
            text=f"Text content for document {i}",
            owner_type="user",
            owner_id=user["id"],
        )
        for i in range(10)
    ]
    assert len(doc_ids) == 10

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": doc_ids, "depth": "standard"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["grounding_metadata"]["contributing_documents"]) == 10


# ---------------------------------------------------------------------------
# Test 6: Ownership isolation enforced (404 on unowned document)
# ---------------------------------------------------------------------------
def test_ownership_isolation_enforced():
    client_a = TestClient(app)
    user_a = _signup_user(client_a, "owner_a_vis@example.com")
    doc_a = _create_ready_doc("Document from A", "doc_a.pdf", user_id=user_a["id"])

    # Client B represents a distinct user
    client_b = TestClient(app)
    _signup_user(client_b, "owner_b_vis@example.com")

    resp = client_b.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc_a["id"]], "depth": "standard"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 7: Guest identity behavior
# ---------------------------------------------------------------------------
def test_guest_identity_behavior(client: TestClient):
    # Unowned / legacy document is accessible to guests
    doc = _create_ready_doc(filename="guest_notes.pdf")

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "standard"},
    )
    assert resp.status_code == 200
    assert resp.json()["grounding_metadata"]["contributing_documents"][0]["id"] == doc["id"]


# ---------------------------------------------------------------------------
# Test 8: Guest AI generation quota enforced (HTTP 403 after 5 generations)
# ---------------------------------------------------------------------------
def test_guest_ai_generation_quota_enforced(client: TestClient):
    doc = _create_ready_doc(filename="guest_quota.pdf")

    # Exhaust the 5 allowed AI generations
    for i in range(5):
        resp = client.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc["id"]], "depth": "overview"},
        )
        assert resp.status_code == 200, f"Call {i+1} failed"

    # 6th call must be rejected with 403 guest_limit_reached
    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "overview"},
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "guest_limit_reached"
    assert detail["limit_type"] == "ai_generation"


# ---------------------------------------------------------------------------
# Test 9: Quota recorded only on success (provider error does not deduct quota)
# ---------------------------------------------------------------------------
def test_quota_recorded_only_on_success(client: TestClient, fake_ai: FakeAIProvider):
    doc = _create_ready_doc(filename="quota_err.pdf")

    # Simulate provider failure
    fake_ai.custom_graph_response = "INVALID NON-JSON OUTPUT"
    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "standard"},
    )
    assert resp.status_code == 502

    # Reset provider to succeed: all 5 quota units should still be intact
    fake_ai.custom_graph_response = None
    for _ in range(5):
        ok_resp = client.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc["id"]], "depth": "standard"},
        )
        assert ok_resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 10: Single unready document rejected with 400
# ---------------------------------------------------------------------------
def test_processing_document_rejected(client: TestClient):
    user = _signup_user(client, "proc_vis@example.com")
    doc_id = _seed_document(
        filename="processing.pdf",
        status="processing",
        owner_type="user",
        owner_id=user["id"],
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc_id], "depth": "standard"},
    )
    assert resp.status_code == 400
    assert "not ready for study" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 11: Single empty document rejected with 422
# ---------------------------------------------------------------------------
def test_empty_document_rejected_single_doc(client: TestClient):
    user = _signup_user(client, "empty_vis@example.com")
    doc_id = _seed_document(
        filename="empty.pdf",
        text="   ",
        status="ready",
        owner_type="user",
        owner_id=user["id"],
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc_id], "depth": "standard"},
    )
    assert resp.status_code == 422
    assert "No readable text was detected" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 12: Mixed readable/unreadable documents in multi-doc selection
# ---------------------------------------------------------------------------
def test_mixed_readable_unreadable_documents_multi_doc(client: TestClient):
    user = _signup_user(client, "mixed_vis@example.com")
    doc_ready_id = _seed_document(
        filename="ready.pdf",
        text="Valid readable text on distributed computing.",
        status="ready",
        owner_type="user",
        owner_id=user["id"],
    )
    doc_unready_id = _seed_document(
        filename="failed.pdf",
        text="",
        status="failed",
        owner_type="user",
        owner_id=user["id"],
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc_ready_id, doc_unready_id], "depth": "standard"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["grounding_metadata"]["contributing_documents"]) == 1
    assert len(data["grounding_metadata"]["excluded_documents"]) == 1
    assert data["grounding_metadata"]["excluded_documents"][0]["id"] == doc_unready_id


# ---------------------------------------------------------------------------
# Test 13: Zero readable documents rejected with 400
# ---------------------------------------------------------------------------
def test_zero_readable_documents_rejected_multi_doc(client: TestClient):
    user = _signup_user(client, "zero_vis@example.com")
    doc1_id = _seed_document(
        filename="f1.pdf",
        text="",
        status="failed",
        owner_type="user",
        owner_id=user["id"],
    )
    doc2_id = _seed_document(
        filename="empty.pdf",
        text="",
        status="ready",
        owner_type="user",
        owner_id=user["id"],
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc1_id, doc2_id], "depth": "standard"},
    )
    assert resp.status_code == 400
    assert "No readable documents available for study" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 14: Bounded graph size enforced
# ---------------------------------------------------------------------------
def test_bounded_graph_size_enforced(client: TestClient, fake_ai: FakeAIProvider):
    user = _signup_user(client, "bounded_vis@example.com")
    doc = _create_ready_doc("Content for bounded test.", user_id=user["id"])

    # Provider generates 30 nodes for overview (which has a limit of 10)
    fake_nodes = [
        {
            "id": f"node_{i}",
            "label": f"Concept {i}",
            "summary": f"Summary {i}",
            "category": "Cat",
            "document_ids": [doc["id"]],
        }
        for i in range(30)
    ]
    fake_edges = [
        {"id": f"edge_{i}", "source": f"node_{i}", "target": f"node_{i+1}", "label": "links"}
        for i in range(29)
    ]

    fake_ai.custom_graph_response = json.dumps(
        {
            "title": "Large Graph",
            "summary": "Too many nodes",
            "nodes": fake_nodes,
            "edges": fake_edges,
        }
    )

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "overview"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Overview max nodes = 10
    assert len(data["nodes"]) <= 10
    node_ids = {n["id"] for n in data["nodes"]}

    # All edges must connect valid nodes within the bounded set
    for edge in data["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids


# ---------------------------------------------------------------------------
# Test 15: AI Provider failure returns 502
# ---------------------------------------------------------------------------
def test_ai_provider_failure_returns_502(client: TestClient, fake_ai: FakeAIProvider):
    user = _signup_user(client, "fail_vis@example.com")
    doc = _create_ready_doc(user_id=user["id"])

    fake_ai.custom_graph_response = "BROKEN NON-JSON"
    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "standard"},
    )
    assert resp.status_code == 502
    assert "Malformed concept graph output" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 16: Revision isolation — Visualize does NOT touch Revision tables
# ---------------------------------------------------------------------------
def test_revision_isolation_visualize_does_not_touch_revision_tables(client: TestClient, db_session):
    user = _signup_user(client, "rev_iso_vis@example.com")
    doc = _create_ready_doc(user_id=user["id"])

    rev_sessions_before = db_session.query(RevisionSession).count()
    rev_questions_before = db_session.query(RevisionQuestion).count()
    rev_attempts_before = db_session.query(RevisionAttempt).count()

    resp = client.post(
        "/api/v1/study/visualize/graph",
        json={"document_ids": [doc["id"]], "depth": "standard"},
    )
    assert resp.status_code == 200

    assert db_session.query(RevisionSession).count() == rev_sessions_before
    assert db_session.query(RevisionQuestion).count() == rev_questions_before
    assert db_session.query(RevisionAttempt).count() == rev_attempts_before
