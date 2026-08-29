import io
import uuid

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import ConversationDocument, Message
from app.main import app

client = TestClient(app)


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_document(filename: str = "test.pdf") -> str:
    """
    Uploads a small real PDF through the actual upload endpoint, same
    as test_document_manager.py's _upload_ready_document -- these
    tests care about conversation/document association behavior, not
    extraction, but going through the real upload flow keeps the
    fixture consistent with the rest of the suite instead of inventing
    a DB-shortcut just for this file.
    """
    pdf_bytes = _make_test_pdf("Some content for conversation tests.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["id"]


# --- create -----------------------------------------------------------


def test_create_empty_conversation():
    response = client.post("/api/v1/conversations", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New Conversation"
    assert body["title_is_custom"] is False
    assert body["documents"] == []
    assert body["messages"] == []
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]


def test_create_conversation_with_documents():
    document_id = _upload_document()

    response = client.post("/api/v1/conversations", json={"document_ids": [document_id]})

    assert response.status_code == 201
    assert [doc["id"] for doc in response.json()["documents"]] == [document_id]


def test_create_conversation_with_invalid_document_id_returns_404():
    response = client.post("/api/v1/conversations", json={"document_ids": [str(uuid.uuid4())]})

    assert response.status_code == 404


def test_create_conversation_dedupes_document_ids():
    document_id = _upload_document()

    response = client.post(
        "/api/v1/conversations", json={"document_ids": [document_id, document_id]}
    )

    assert response.status_code == 201
    assert len(response.json()["documents"]) == 1


# --- list / get ---------------------------------------------------------


def test_list_conversations_returns_created_conversations():
    first = client.post("/api/v1/conversations", json={}).json()
    second = client.post("/api/v1/conversations", json={}).json()

    response = client.get("/api/v1/conversations")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert first["id"] in ids
    assert second["id"] in ids


def test_get_conversation_returns_full_detail():
    created = client.post("/api/v1/conversations", json={}).json()

    response = client.get(f"/api/v1/conversations/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["documents"] == []
    assert body["messages"] == []


def test_get_missing_conversation_returns_404():
    response = client.get(f"/api/v1/conversations/{uuid.uuid4()}")

    assert response.status_code == 404


# --- rename ---------------------------------------------------------


def test_rename_conversation_sets_custom_flag():
    created = client.post("/api/v1/conversations", json={}).json()

    response = client.patch(
        f"/api/v1/conversations/{created['id']}", json={"title": "Deadlocks study session"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Deadlocks study session"
    assert body["title_is_custom"] is True


def test_rename_conversation_rejects_blank_title():
    created = client.post("/api/v1/conversations", json={}).json()

    response = client.patch(f"/api/v1/conversations/{created['id']}", json={"title": "   "})

    assert response.status_code == 422


def test_rename_missing_conversation_returns_404():
    response = client.patch(f"/api/v1/conversations/{uuid.uuid4()}", json={"title": "Anything"})

    assert response.status_code == 404


# --- document association -----------------------------------------------


def test_replace_conversation_documents():
    document_a = _upload_document("a.pdf")
    document_b = _upload_document("b.pdf")
    created = client.post("/api/v1/conversations", json={"document_ids": [document_a]}).json()

    response = client.put(
        f"/api/v1/conversations/{created['id']}/documents",
        json={"document_ids": [document_b]},
    )

    assert response.status_code == 200
    assert [doc["id"] for doc in response.json()["documents"]] == [document_b]


def test_replace_conversation_documents_with_empty_list_clears_documents():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    response = client.put(
        f"/api/v1/conversations/{created['id']}/documents", json={"document_ids": []}
    )

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_replace_conversation_documents_dedupes_ids():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={}).json()

    response = client.put(
        f"/api/v1/conversations/{created['id']}/documents",
        json={"document_ids": [document_id, document_id]},
    )

    assert response.status_code == 200
    assert len(response.json()["documents"]) == 1


def test_replace_documents_with_invalid_document_id_returns_404_and_leaves_existing_association():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    response = client.put(
        f"/api/v1/conversations/{created['id']}/documents",
        json={"document_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 404

    # the failed replace attempt must not have touched the existing association
    follow_up = client.get(f"/api/v1/conversations/{created['id']}")
    assert [doc["id"] for doc in follow_up.json()["documents"]] == [document_id]


def test_replace_documents_on_missing_conversation_returns_404():
    response = client.put(
        f"/api/v1/conversations/{uuid.uuid4()}/documents", json={"document_ids": []}
    )

    assert response.status_code == 404


def test_same_document_can_belong_to_multiple_conversations():
    document_id = _upload_document()

    first = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()
    second = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    assert first["id"] != second["id"]
    assert [doc["id"] for doc in first["documents"]] == [document_id]
    assert [doc["id"] for doc in second["documents"]] == [document_id]


def test_conversation_document_association_is_isolated_per_conversation():
    """
    Conversation isolation, extended to document associations: two
    conversations with different documents must never leak into each
    other, and (in test_list_conversations_returns_created_conversations
    and the message-deletion tests below) two conversations' messages
    must never leak into each other either.
    """
    document_a = _upload_document("iso-a.pdf")
    document_b = _upload_document("iso-b.pdf")

    conversation_a = client.post(
        "/api/v1/conversations", json={"document_ids": [document_a]}
    ).json()
    conversation_b = client.post(
        "/api/v1/conversations", json={"document_ids": [document_b]}
    ).json()

    response_a = client.get(f"/api/v1/conversations/{conversation_a['id']}")
    response_b = client.get(f"/api/v1/conversations/{conversation_b['id']}")

    assert [doc["id"] for doc in response_a.json()["documents"]] == [document_a]
    assert [doc["id"] for doc in response_b.json()["documents"]] == [document_b]


# --- deletion ---------------------------------------------------------


def test_delete_conversation_removes_it():
    created = client.post("/api/v1/conversations", json={}).json()

    response = client.delete(f"/api/v1/conversations/{created['id']}")
    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/conversations/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_missing_conversation_returns_404():
    response = client.delete(f"/api/v1/conversations/{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_conversation_preserves_its_documents():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    client.delete(f"/api/v1/conversations/{created['id']}")

    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200


def test_delete_conversation_removes_its_document_associations():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    client.delete(f"/api/v1/conversations/{created['id']}")

    db = SessionLocal()
    try:
        remaining = (
            db.query(ConversationDocument)
            .filter(ConversationDocument.conversation_id == created["id"])
            .count()
        )
        assert remaining == 0
    finally:
        db.close()


def test_delete_conversation_removes_its_messages():
    created = client.post("/api/v1/conversations", json={}).json()

    # No message-creation endpoint exists yet -- that's Milestone 2.
    # Inserted directly to exercise delete_conversation's cleanup
    # against the Message model this milestone already adds.
    db = SessionLocal()
    try:
        db.add(
            Message(
                conversation_id=created["id"],
                role="user",
                content="What is a deadlock?",
                position=1,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.delete(f"/api/v1/conversations/{created['id']}")
    assert response.status_code == 204

    db = SessionLocal()
    try:
        remaining = db.query(Message).filter(Message.conversation_id == created["id"]).count()
        assert remaining == 0
    finally:
        db.close()


# --- document deletion / stale references --------------------------------


def test_deleting_a_document_removes_its_conversation_association_but_not_the_conversation():
    document_id = _upload_document()
    created = client.post("/api/v1/conversations", json={"document_ids": [document_id]}).json()

    delete_response = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_response.status_code == 204

    follow_up = client.get(f"/api/v1/conversations/{created['id']}")
    assert follow_up.status_code == 200
    assert follow_up.json()["documents"] == []


def test_deleting_a_document_referenced_by_multiple_conversations_clears_it_from_all_of_them():
    document_id = _upload_document()
    conversation_a = client.post(
        "/api/v1/conversations", json={"document_ids": [document_id]}
    ).json()
    conversation_b = client.post(
        "/api/v1/conversations", json={"document_ids": [document_id]}
    ).json()

    client.delete(f"/api/v1/documents/{document_id}")

    assert client.get(f"/api/v1/conversations/{conversation_a['id']}").json()["documents"] == []
    assert client.get(f"/api/v1/conversations/{conversation_b['id']}").json()["documents"] == []


def test_mixed_valid_and_missing_documents_in_a_conversation():
    keep_document = _upload_document("keep.pdf")
    remove_document = _upload_document("remove.pdf")
    created = client.post(
        "/api/v1/conversations",
        json={"document_ids": [keep_document, remove_document]},
    ).json()

    client.delete(f"/api/v1/documents/{remove_document}")

    response = client.get(f"/api/v1/conversations/{created['id']}")
    assert response.status_code == 200
    assert [doc["id"] for doc in response.json()["documents"]] == [keep_document]


# --- timestamp timezone (V2.4 Milestone 2 Phase 3 QA, issue 2) --------
#
# SQLite drops tzinfo from every DateTime column on write (see
# db/models.py's `datetime.now(timezone.utc)` default -- the column
# itself has no `timezone=True`, since SQLite has no native
# timezone-aware type to back one). Reading a row back therefore
# yields a *naive* datetime whose digits are UTC but whose `tzinfo` is
# None. Serializing that naively (no explicit offset) is what caused
# the actual manual-QA bug: a browser's `new Date(isoString)` treats
# an offset-less ISO-8601 string as *local* time, not UTC, so a
# conversation created moments ago showed as several hours old for
# anyone not in UTC+0. These tests assert the API response always
# carries an explicit UTC marker so that ambiguity can never reach the
# frontend -- see schemas/conversation.py's `_assume_utc`.


def test_new_conversation_timestamps_carry_explicit_utc_offset():
    created = client.post("/api/v1/conversations", json={}).json()

    for field in ("created_at", "updated_at"):
        value = created[field]
        assert value.endswith("Z") or "+" in value.split("T", 1)[1], (
            f"{field}={value!r} has no explicit UTC offset -- a client's "
            "new Date(...) would parse it as local time, not UTC."
        )


def test_get_conversation_timestamps_carry_explicit_utc_offset():
    created = client.post("/api/v1/conversations", json={}).json()

    fetched = client.get(f"/api/v1/conversations/{created['id']}").json()
    for field in ("created_at", "updated_at"):
        value = fetched[field]
        assert value.endswith("Z") or "+" in value.split("T", 1)[1]


def test_new_conversation_created_at_is_actually_recent():
    """
    The real symptom reported in manual QA: not just "no offset", but
    a freshly created conversation's timestamp parsing as if it were
    hours in the past. Parses the response the same way a spec-
    compliant client would (fromisoformat handles both "Z" and
    "+00:00" once normalized) and asserts it lands within a few
    seconds of "now" -- proving there's no hidden multi-hour skew, not
    just that a suffix is present.
    """
    from datetime import datetime, timedelta, timezone

    before = datetime.now(timezone.utc)
    created = client.post("/api/v1/conversations", json={}).json()
    after = datetime.now(timezone.utc)

    parsed = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert before - timedelta(seconds=2) <= parsed <= after + timedelta(seconds=2)
