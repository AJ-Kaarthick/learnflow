"""
V3 Milestone 1 Phase 3: data isolation.

Covers app/services/ownership_service.py's enforcement across every
identity pairing this phase's brief calls out: guest vs. guest, user
vs. user, an authenticated user against an unrelated guest's data, and
a guest against an authenticated user's data. In every case, a
document or conversation that isn't owned by the requesting identity
must behave as if it doesn't exist at all (404, not a 403 or some
other status that would confirm something is there) -- see
ownership_service.is_owned_by's own docstring for why leaking that
distinction matters.

Two different TestClient instances are used for two different guest
identities, the same isolation setup test_identity_session.py and
test_auth.py already establish (a fresh TestClient has a fresh, empty
cookie jar, hence a brand new guest session on its first request).
"""

import io
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app

SIGNUP_URL = "/api/v1/auth/signup"
UPLOAD_URL = "/api/v1/documents/upload"

VALID_PASSWORD = "Correct-Horse1!"


def _unique_email(label: str) -> str:
    return f"{label}.{datetime.now(timezone.utc).timestamp()}@example.com"


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload(client: TestClient, filename: str, text: str) -> str:
    response = client.post(
        UPLOAD_URL, files={"file": (filename, _make_test_pdf(text), "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _sign_up(client: TestClient, label: str) -> dict:
    response = client.post(
        SIGNUP_URL, json={"email": _unique_email(label), "password": VALID_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Guest vs. guest --------------------------------------------------


def test_guest_cannot_access_another_guests_document():
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    document_id = _upload(guest_a, "a-only.pdf", "Guest A's private document.")

    response = guest_b.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 404


def test_guest_cannot_see_another_guests_document_in_their_library():
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    _upload(guest_a, "a-only.pdf", "Guest A's private document.")
    _upload(guest_b, "b-only.pdf", "Guest B's private document.")

    library_b = guest_b.get("/api/v1/documents")

    assert library_b.status_code == 200
    filenames = {document["original_filename"] for document in library_b.json()}
    assert filenames == {"b-only.pdf"}


def test_guest_cannot_rename_another_guests_document():
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    document_id = _upload(guest_a, "a-only.pdf", "Guest A's private document.")

    response = guest_b.patch(
        f"/api/v1/documents/{document_id}", json={"original_filename": "hijacked.pdf"}
    )

    assert response.status_code == 404


def test_guest_cannot_delete_another_guests_document():
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    document_id = _upload(guest_a, "a-only.pdf", "Guest A's private document.")

    response = guest_b.delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 404
    # The document is genuinely still there for its real owner -- this
    # wasn't silently a no-op delete, it was a real "not found" refusal.
    assert guest_a.get(f"/api/v1/documents/{document_id}").status_code == 200


def test_guest_cannot_access_another_guests_conversation():
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    conversation_id = guest_a.post("/api/v1/conversations", json={"document_ids": []}).json()["id"]

    response = guest_b.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 404


def test_guest_cannot_associate_another_guests_document_with_their_own_conversation():
    """
    Defense at the point of association, not just at read time -- a
    guest can't launder access to someone else's document by attaching
    it to a conversation they DO own, which is exactly what would
    later let them read its content through conversation chat.
    """
    guest_a = TestClient(app)
    guest_b = TestClient(app)
    document_id = _upload(guest_a, "a-only.pdf", "Guest A's private document.")
    conversation_id = guest_b.post("/api/v1/conversations", json={"document_ids": []}).json()["id"]

    response = guest_b.put(
        f"/api/v1/conversations/{conversation_id}/documents", json={"document_ids": [document_id]}
    )

    assert response.status_code == 404


# --- User vs. user ------------------------------------------------------


def test_authenticated_user_cannot_access_another_users_document():
    user_a = TestClient(app)
    user_b = TestClient(app)
    _sign_up(user_a, "user-a")
    _sign_up(user_b, "user-b")
    document_id = _upload(user_a, "a-only.pdf", "User A's private document.")

    response = user_b.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 404


def test_authenticated_user_cannot_access_another_users_conversation():
    user_a = TestClient(app)
    user_b = TestClient(app)
    _sign_up(user_a, "convo-user-a")
    _sign_up(user_b, "convo-user-b")
    conversation_id = user_a.post("/api/v1/conversations", json={"document_ids": []}).json()["id"]

    response = user_b.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 404


def test_authenticated_users_document_library_only_shows_their_own_documents():
    user_a = TestClient(app)
    user_b = TestClient(app)
    _sign_up(user_a, "library-user-a")
    _sign_up(user_b, "library-user-b")
    _upload(user_a, "a-only.pdf", "User A's document.")
    _upload(user_b, "b-only.pdf", "User B's document.")

    library_a = user_a.get("/api/v1/documents")

    filenames = {document["original_filename"] for document in library_a.json()}
    assert filenames == {"a-only.pdf"}


# --- Authenticated user vs. unrelated guest -----------------------------


def test_authenticated_user_cannot_access_an_unrelated_guests_document():
    guest = TestClient(app)
    user = TestClient(app)
    _sign_up(user, "unrelated-user")
    document_id = _upload(guest, "guest-only.pdf", "An unrelated guest's document.")

    response = user.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 404


def test_authenticated_user_cannot_access_an_unrelated_guests_conversation():
    guest = TestClient(app)
    user = TestClient(app)
    _sign_up(user, "unrelated-user-convo")
    conversation_id = guest.post("/api/v1/conversations", json={"document_ids": []}).json()["id"]

    response = user.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 404


# --- Guest vs. authenticated user ----------------------------------------


def test_guest_cannot_access_an_authenticated_users_document():
    user = TestClient(app)
    guest = TestClient(app)
    _sign_up(user, "target-user")
    document_id = _upload(user, "user-only.pdf", "An authenticated user's document.")

    response = guest.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 404


def test_guest_cannot_access_an_authenticated_users_conversation():
    user = TestClient(app)
    guest = TestClient(app)
    _sign_up(user, "target-user-convo")
    conversation_id = user.post("/api/v1/conversations", json={"document_ids": []}).json()["id"]

    response = guest.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 404
