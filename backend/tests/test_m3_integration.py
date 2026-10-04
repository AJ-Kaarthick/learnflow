import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import (
    Document,
    DocumentChunk,
    GuestSession,
    RevisionAttempt,
    RevisionQuestion,
    RevisionSession,
)
from app.main import app
from app.services import guest_session_service
from app.services.ai.base_provider import AIProvider
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.rag.embedding_service import index_document


class M3IntegrationEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for vector similarity tests."""

    async def embed_document(self, text: str) -> list[float]:
        return [1.0, 0.0]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class M3IntegrationAIProvider(AIProvider):
    """
    Unified mock AI provider for Milestone 3 cross-phase integration tests.
    Dispatches realistic structured responses for:
    - Study Learn curriculum outline
    - Study Learn topic deep dive (with key terms, takeaways)
    - Study Visualize concept network graph (with multi-document attribution)
    """

    def __init__(self, doc1_id: str, doc2_id: str) -> None:
        self.doc1_id = doc1_id
        self.doc2_id = doc2_id
        self.call_count = 0
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        prompt_lower = prompt.lower()

        if "concept network" in prompt_lower or "concept graph" in prompt_lower or "visualizer" in prompt_lower or "visualize" in prompt_lower:
            return json.dumps(
                {
                    "title": "Systems Concurrency and Distributed Coordination Graph",
                    "summary": "Conceptual network mapping relationships between OS concurrency and distributed databases.",
                    "nodes": [
                        {
                            "id": "concept-os-sync",
                            "label": "Process Synchronization",
                            "summary": "Mechanisms ensuring concurrent processes execute without data corruption.",
                            "category": "Operating Systems",
                            "document_ids": [self.doc1_id],
                            "importance": 2.2,
                        },
                        {
                            "id": "concept-db-tx",
                            "label": "Distributed Transactions",
                            "summary": "Coordinated database operations across independent nodes maintaining ACID.",
                            "category": "Databases",
                            "document_ids": [self.doc2_id],
                            "importance": 2.0,
                        },
                        {
                            "id": "concept-cross-consensus",
                            "label": "Mutual Exclusion & Consensus",
                            "summary": "Fundamental coordination principles spanning single-node OS and multi-node clusters.",
                            "category": "Cross-Cutting",
                            "document_ids": [self.doc1_id, self.doc2_id],
                            "importance": 2.5,
                        },
                    ],
                    "edges": [
                        {
                            "id": "edge-os-cross",
                            "source": "concept-os-sync",
                            "target": "concept-cross-consensus",
                            "label": "generalizes to",
                        },
                        {
                            "id": "edge-db-cross",
                            "source": "concept-db-tx",
                            "target": "concept-cross-consensus",
                            "label": "relies on",
                        },
                    ],
                }
            )

        if "curriculum" in prompt_lower or "study outline" in prompt_lower:
            return json.dumps(
                {
                    "title": "Integrated Systems and Concurrency",
                    "description": "Cross-document study curriculum on Operating Systems and Distributed Databases.",
                    "learning_objectives": [
                        "Understand process scheduling and synchronization primitives",
                        "Master distributed transaction isolation and two-phase commit protocols",
                    ],
                    "topics": [
                        {
                            "id": "topic-os-1",
                            "title": "Processes and Concurrency",
                            "description": "Foundations of process scheduling and multi-threading.",
                            "learning_objectives": [
                                "Differentiate process vs thread memory spaces",
                                "Identify critical section race conditions",
                            ],
                            "subtopics": [
                                {
                                    "id": "subtopic-os-1-1",
                                    "title": "Mutexes and Semaphores",
                                    "summary": "Synchronization primitives preventing concurrent data corruption.",
                                }
                            ],
                        },
                        {
                            "id": "topic-db-1",
                            "title": "Distributed Transactions",
                            "description": "ACID guarantees and distributed concurrency control.",
                            "learning_objectives": [
                                "Analyze two-phase locking protocols",
                                "Understand two-phase commit consensus",
                            ],
                            "subtopics": [
                                {
                                    "id": "subtopic-db-1-1",
                                    "title": "Two-Phase Commit Protocol",
                                    "summary": "Atomic distributed commit across coordinator and participants.",
                                }
                            ],
                        },
                    ],
                }
            )

        # Default to Learn Topic explanation
        return json.dumps(
            {
                "explanation": (
                    "Processes and concurrency form the bedrock of multi-tasking computing systems. "
                    "Processes maintain isolated virtual memory addresses, while threads run concurrently "
                    "within the shared address space. Synchronization primitives such as mutexes prevent "
                    "race conditions, while distributed systems extend these guarantees across networks "
                    "using atomic commitment protocols."
                ),
                "key_terms": [
                    {
                        "term": "Process",
                        "definition": "An execution context with dedicated virtual memory and system resources.",
                    },
                    {
                        "term": "Mutex",
                        "definition": "A mutual exclusion lock that serializes access to critical sections.",
                    },
                ],
                "key_takeaways": [
                    "Isolated address spaces protect processes from corrupting each other.",
                    "Multi-threading requires strict synchronization to prevent nondeterministic race conditions.",
                    "Distributed systems coordinate concurrent state using protocols like two-phase commit.",
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


def _create_m3_guest_session(db) -> str:
    guest = guest_session_service.create_guest_session(db)
    return guest.id


def _seed_m3_document(
    db,
    doc_id: str,
    filename: str,
    text: str,
    status: str = "ready",
    owner_id: str | None = None,
) -> Document:
    doc = Document(
        id=doc_id,
        original_filename=filename,
        stored_filename=filename,
        status=status,
        extracted_text=text,
        owner_type="guest" if owner_id else None,
        owner_id=owner_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_m3_end_to_end_guest_flow(db_session):
    """
    Milestone 3 Phase 5 Core Integration Verification:
    1. Establish guest session identity and cookie.
    2. Seed two readable documents owned by that guest identity.
    3. Index documents into RAG vector storage.
    4. Call POST /api/v1/study/learn/outline across both documents.
    5. Verify 200 OK, topics, multi-document contributing metadata, guest quota = 1.
    6. Call POST /api/v1/study/learn/topic for one topic.
    7. Verify 200 OK, grounded explanation, key terms, takeaways, source citations, guest quota = 2.
    8. Call POST /api/v1/study/visualize/graph across both documents.
    9. Verify 200 OK, nodes, edges, cross-document concept attribution, citations, guest quota = 3.
    10. Verify guest AI generation limit accounting: exactly 3 generations counted.
    11. Verify Revision table isolation: confirm RevisionSession, Question, Attempt counts remain 0.
    """
    guest_id = _create_m3_guest_session(db_session)
    client = TestClient(app)
    client.cookies.set(settings.guest_session_cookie_name, guest_id)

    doc1_text = (
        "Operating systems govern hardware resources and process execution. "
        "A process defines a private virtual memory space and execution context. "
        "Threads share the process memory space while running concurrently. "
        "Mutexes and binary semaphores enforce mutual exclusion in critical sections to prevent race conditions. "
    ) * 10

    doc2_text = (
        "Distributed database systems provide reliable data management across interconnected computer nodes. "
        "Transactions maintain ACID properties: Atomicity, Consistency, Isolation, and Durability. "
        "Two-phase commit coordinates transactions across distributed nodes to guarantee atomic commitment. "
        "Concurrency control protocols like two-phase locking preserve strict serializability. "
    ) * 10

    doc_os = _seed_m3_document(
        db_session,
        doc_id="m3-int-os-01",
        filename="Operating_Systems_Concurrency.pdf",
        text=doc1_text,
        owner_id=guest_id,
    )
    doc_db = _seed_m3_document(
        db_session,
        doc_id="m3-int-db-01",
        filename="Distributed_Databases_Tx.pdf",
        text=doc2_text,
        owner_id=guest_id,
    )

    fake_embed = M3IntegrationEmbeddingProvider()
    fake_ai = M3IntegrationAIProvider(doc1_id=doc_os.id, doc2_id=doc_db.id)

    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embed

    try:
        # Pre-index chunks to verify retrieval indexing
        asyncio.run(index_document(doc_os, db_session, fake_embed))
        asyncio.run(index_document(doc_db, db_session, fake_embed))

        os_chunks = (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc_os.id)
            .count()
        )
        db_chunks = (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc_db.id)
            .count()
        )
        assert os_chunks > 0, "Expected doc_os to have indexed chunks"
        assert db_chunks > 0, "Expected doc_db to have indexed chunks"

        # Pre-condition: Record Revision table baseline counts
        initial_revision_sessions = db_session.query(RevisionSession).count()
        initial_revision_questions = db_session.query(RevisionQuestion).count()
        initial_revision_attempts = db_session.query(RevisionAttempt).count()

        # Step 4: POST /api/v1/study/learn/outline
        resp_outline = client.post(
            "/api/v1/study/learn/outline",
            json={"document_ids": [doc_os.id, doc_db.id], "depth": "standard"},
        )
        assert resp_outline.status_code == 200
        outline_data = resp_outline.json()

        assert outline_data["document_ids"] == [doc_os.id, doc_db.id]
        assert len(outline_data["topics"]) == 2
        assert outline_data["topics"][0]["id"] == "topic-os-1"
        assert outline_data["topics"][1]["id"] == "topic-db-1"

        contributing = outline_data["grounding_metadata"]["contributing_documents"]
        contributing_ids = [d["id"] for d in contributing]
        assert doc_os.id in contributing_ids
        assert doc_db.id in contributing_ids
        assert outline_data["grounding_metadata"]["excluded_documents"] == []

        # Verify quota incremented to 1
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 1

        # Step 6: POST /api/v1/study/learn/topic
        resp_topic = client.post(
            "/api/v1/study/learn/topic",
            json={
                "document_ids": [doc_os.id, doc_db.id],
                "topic_id": "topic-os-1",
                "topic_title": "Processes and Concurrency",
                "action": "elaborate",
                "depth": "standard",
            },
        )
        assert resp_topic.status_code == 200
        topic_data = resp_topic.json()

        assert topic_data["topic_id"] == "topic-os-1"
        assert topic_data["action"] == "elaborate"
        assert "Processes and concurrency" in topic_data["explanation"]
        assert len(topic_data["key_terms"]) >= 1
        assert len(topic_data["key_takeaways"]) >= 1
        assert len(topic_data["sources"]) > 0
        assert topic_data["grounding_metadata"]["grounded"] is True
        assert topic_data["grounding_metadata"]["retrieved_chunks_count"] > 0

        # Verify quota incremented to 2
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 2

        # Step 8: POST /api/v1/study/visualize/graph
        resp_visualize = client.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc_os.id, doc_db.id], "depth": "standard"},
        )
        assert resp_visualize.status_code == 200
        vis_data = resp_visualize.json()

        assert vis_data["document_ids"] == [doc_os.id, doc_db.id]
        assert len(vis_data["nodes"]) == 3
        assert len(vis_data["edges"]) == 2

        # Verify cross-document concept attribution
        cross_doc_nodes = [
            node for node in vis_data["nodes"]
            if doc_os.id in node["document_ids"] and doc_db.id in node["document_ids"]
        ]
        assert len(cross_doc_nodes) == 1
        assert cross_doc_nodes[0]["id"] == "concept-cross-consensus"

        # Verify grounded source citations for visualize concepts
        assert len(vis_data["citations"]) > 0
        for citation in vis_data["citations"]:
            assert citation["document_id"] in [doc_os.id, doc_db.id]
            assert citation["chunk_id"] is not None
            assert citation["score"] > 0

        # Step 10: Verify guest AI generation limit accounting: exactly 3
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 3
        assert guest_row.document_upload_count == 0
        assert guest_row.chat_message_count == 0

        # Step 11: Verify Revision table isolation: counts untouched, no guest rows created
        assert db_session.query(RevisionSession).count() == initial_revision_sessions
        assert db_session.query(RevisionQuestion).count() == initial_revision_questions
        assert db_session.query(RevisionAttempt).count() == initial_revision_attempts
        assert (
            db_session.query(RevisionSession)
            .filter(RevisionSession.owner_id == guest_id)
            .count()
            == 0
        )

    finally:
        app.dependency_overrides.clear()


def test_m3_readiness_boundary_and_exclusions(db_session):
    """
    Milestone 3 Phase 5 Document Readiness Boundary Verification:
    - Mixed readable and unreadable documents succeed with partial readable content.
    - Server returns accurate contributing_documents and excluded_documents.
    - Zero readable documents triggers strict 400 Bad Request error.
    - Unsuccessful requests do NOT consume guest AI generation quota.
    """
    guest_id = _create_m3_guest_session(db_session)
    client = TestClient(app)
    client.cookies.set(settings.guest_session_cookie_name, guest_id)

    doc_ready = _seed_m3_document(
        db_session,
        doc_id="m3-bound-ready-01",
        filename="valid_os_notes.pdf",
        text="Valid operating system concepts with threads, processes, and memory. " * 8,
        owner_id=guest_id,
    )
    doc_proc = _seed_m3_document(
        db_session,
        doc_id="m3-bound-proc-01",
        filename="still_processing.pdf",
        text="",
        status="processing",
        owner_id=guest_id,
    )
    doc_empty = _seed_m3_document(
        db_session,
        doc_id="m3-bound-empty-01",
        filename="empty_file.pdf",
        text="   \n  \t  ",
        status="ready",
        owner_id=guest_id,
    )

    fake_embed = M3IntegrationEmbeddingProvider()
    fake_ai = M3IntegrationAIProvider(doc1_id=doc_ready.id, doc2_id=doc_ready.id)

    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embed

    try:
        # A. Learn Outline with mixed readiness: 1 ready, 1 processing, 1 empty
        resp_mix_outline = client.post(
            "/api/v1/study/learn/outline",
            json={"document_ids": [doc_ready.id, doc_proc.id, doc_empty.id]},
        )
        assert resp_mix_outline.status_code == 200
        out_data = resp_mix_outline.json()

        contributing = [d["id"] for d in out_data["grounding_metadata"]["contributing_documents"]]
        assert contributing == [doc_ready.id]

        excluded = out_data["grounding_metadata"]["excluded_documents"]
        excluded_map = {d["id"]: d["reason"] for d in excluded}
        assert doc_proc.id in excluded_map
        assert "processing" in excluded_map[doc_proc.id].lower()
        assert doc_empty.id in excluded_map
        assert "readable_text" in excluded_map[doc_empty.id].lower()

        # B. Visualize Graph with mixed readiness: 1 ready, 1 processing
        resp_mix_vis = client.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc_ready.id, doc_proc.id]},
        )
        assert resp_mix_vis.status_code == 200
        vis_data = resp_mix_vis.json()

        assert [d["id"] for d in vis_data["grounding_metadata"]["contributing_documents"]] == [doc_ready.id]
        assert doc_proc.id in [d["id"] for d in vis_data["grounding_metadata"]["excluded_documents"]]

        # Quota check after 2 successful generations
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 2

        # C. All-unreadable outline request -> 400 Bad Request
        resp_zero_outline = client.post(
            "/api/v1/study/learn/outline",
            json={"document_ids": [doc_proc.id, doc_empty.id]},
        )
        assert resp_zero_outline.status_code == 400
        assert "readable text" in resp_zero_outline.json()["detail"].lower()

        # D. All-unreadable topic request -> 400 Bad Request
        resp_zero_topic = client.post(
            "/api/v1/study/learn/topic",
            json={
                "document_ids": [doc_proc.id, doc_empty.id],
                "topic_id": "topic-1",
                "topic_title": "Threads",
            },
        )
        assert resp_zero_topic.status_code == 400

        # E. All-unreadable visualize request -> 400 Bad Request
        resp_zero_vis = client.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc_proc.id, doc_empty.id]},
        )
        assert resp_zero_vis.status_code == 400
        assert "readable text" in resp_zero_vis.json()["detail"].lower()

        # Quota must NOT have been incremented by the 3 failed 400 requests
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 2

    finally:
        app.dependency_overrides.clear()


def test_m3_quota_exhaustion_cross_modal(monkeypatch, db_session):
    """
    Milestone 3 Phase 5 Quota Exhaustion Across Learn & Visualize Modes:
    When a guest reaches settings.guest_max_ai_generations (e.g. 2 calls),
    both /study/learn and /study/visualize endpoints enforce a 403 Forbidden
    guest_limit_reached response and reject further calls without invoking AI.
    """
    monkeypatch.setattr(settings, "guest_max_ai_generations", 2)

    guest_id = _create_m3_guest_session(db_session)
    client = TestClient(app)
    client.cookies.set(settings.guest_session_cookie_name, guest_id)

    doc = _seed_m3_document(
        db_session,
        doc_id="m3-quota-doc-01",
        filename="quota_demo.pdf",
        text="Content for testing guest generation limits across modes. " * 10,
        owner_id=guest_id,
    )

    fake_embed = M3IntegrationEmbeddingProvider()
    fake_ai = M3IntegrationAIProvider(doc1_id=doc.id, doc2_id=doc.id)

    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embed

    try:
        # Call 1: Learn outline -> consumes 1 of 2
        r1 = client.post("/api/v1/study/learn/outline", json={"document_ids": [doc.id]})
        assert r1.status_code == 200

        # Call 2: Visualize graph -> consumes 2 of 2
        r2 = client.post("/api/v1/study/visualize/graph", json={"document_ids": [doc.id]})
        assert r2.status_code == 200

        # Verify 2 calls consumed
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 2

        # Call 3: Learn topic -> exceeds limit -> 403
        r3 = client.post(
            "/api/v1/study/learn/topic",
            json={"document_ids": [doc.id], "topic_id": "top-1", "topic_title": "Threads"},
        )
        assert r3.status_code == 403
        assert r3.json()["detail"]["code"] == "guest_limit_reached"
        assert r3.json()["detail"]["limit_type"] == "ai_generation"

        # Call 4: Visualize graph -> exceeds limit -> 403
        r4 = client.post("/api/v1/study/visualize/graph", json={"document_ids": [doc.id]})
        assert r4.status_code == 403
        assert r4.json()["detail"]["code"] == "guest_limit_reached"

        # Quota remains capped at 2
        db_session.expire_all()
        guest_row = db_session.query(GuestSession).filter(GuestSession.id == guest_id).first()
        assert guest_row.ai_generation_count == 2

    finally:
        app.dependency_overrides.clear()


def test_m3_cross_identity_isolation(db_session):
    """
    Milestone 3 Phase 5 Cross-Identity Isolation Verification:
    Documents owned by guest session A are inaccessible to guest session B.
    Attempts to generate Learn outlines or Visualize graphs for unowned documents
    are blocked with 400 Bad Request.
    """
    guest_a_id = _create_m3_guest_session(db_session)
    guest_b_id = _create_m3_guest_session(db_session)

    doc_a = _seed_m3_document(
        db_session,
        doc_id="m3-iso-doc-a",
        filename="guest_a_private.pdf",
        text="Private material strictly owned by guest A. " * 10,
        owner_id=guest_a_id,
    )

    client_b = TestClient(app)
    client_b.cookies.set(settings.guest_session_cookie_name, guest_b_id)

    fake_embed = M3IntegrationEmbeddingProvider()
    fake_ai = M3IntegrationAIProvider(doc1_id=doc_a.id, doc2_id=doc_a.id)

    app.dependency_overrides[get_ai_provider] = lambda: fake_ai
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embed

    try:
        # Guest B attempts to request Learn outline for Guest A's document
        resp_learn = client_b.post(
            "/api/v1/study/learn/outline",
            json={"document_ids": [doc_a.id]},
        )
        assert resp_learn.status_code == 404
        assert "not found" in resp_learn.json()["detail"].lower()

        # Guest B attempts to request Visualize graph for Guest A's document
        resp_vis = client_b.post(
            "/api/v1/study/visualize/graph",
            json={"document_ids": [doc_a.id]},
        )
        assert resp_vis.status_code == 404
        assert "not found" in resp_vis.json()["detail"].lower()

        # Neither call invoked AI nor consumed Guest B's quota
        db_session.expire_all()
        guest_b = db_session.query(GuestSession).filter(GuestSession.id == guest_b_id).first()
        assert guest_b.ai_generation_count == 0

    finally:
        app.dependency_overrides.clear()
