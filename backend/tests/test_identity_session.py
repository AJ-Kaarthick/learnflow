"""
V3 Milestone 1 Phase 1: guest identity/session foundation.

Covers the identity resolution built in app/api/deps.py and
app/services/guest_session_service.py -- HTTP-level behavior through
GET /api/v1/identity/me (new guest creation, persistence across
requests and across unrelated endpoints, isolation between separate
clients, and safe handling of a missing/garbage cookie), plus
service-level behavior for expiration and activity that's awkward to
assert precisely through the HTTP layer alone.

Per this phase's brief ("Prefer deterministic tests for expiration
rather than waiting real minutes"), expiration here is simulated by
directly backdating a session's `last_seen_at` in the database rather
than sleeping or mocking the system clock -- deterministic, and fast
regardless of how `guest_session_inactivity_minutes` is configured.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import GuestSession
from app.main import app
from app.services import guest_session_service

IDENTITY_URL = "/api/v1/identity/me"


def _backdate_last_seen(session_id: str, minutes_ago: float) -> None:
    """
    Directly rewrites a GuestSession row's `last_seen_at` to simulate
    inactivity, bypassing the need to sleep or mock the clock.
    """
    db = SessionLocal()
    try:
        session = db.query(GuestSession).filter(GuestSession.id == session_id).first()
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        db.commit()
    finally:
        db.close()


# --- New session creation ----------------------------------------------


def test_new_guest_session_is_created_on_first_request():
    client = TestClient(app)

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "guest"
    assert body["id"]
    # A real cookie was issued -- this is what lets the *next* request
    # from the same browser resolve back to this same identity.
    assert settings.guest_session_cookie_name in response.cookies


def test_missing_cookie_is_treated_as_a_new_guest_not_an_error():
    client = TestClient(app)

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200


# --- Guest identity persistence -----------------------------------------


def test_guest_identity_persists_across_multiple_requests():
    client = TestClient(app)

    first = client.get(IDENTITY_URL).json()
    second = client.get(IDENTITY_URL).json()
    third = client.get(IDENTITY_URL).json()

    assert first["id"] == second["id"] == third["id"]


def test_guest_identity_persists_across_unrelated_api_calls():
    """
    The guest session isn't special-cased to only survive if you keep
    hitting /identity/me -- any normal API call from the same client
    (e.g. listing documents) resolves to, and keeps alive, the same
    guest identity. Mirrors the phase brief's "Library -> Study -> Chat
    -> still Guest A" navigation example.
    """
    client = TestClient(app)

    identity_before = client.get(IDENTITY_URL).json()
    documents_response = client.get("/api/v1/documents")
    assert documents_response.status_code == 200
    identity_after = client.get(IDENTITY_URL).json()

    assert identity_before["id"] == identity_after["id"]


# --- Guest isolation ------------------------------------------------------


def test_different_clients_get_isolated_guest_identities():
    """
    Two separate browsers/sessions (modeled here as two separate
    TestClient instances, each with its own cookie jar) must never
    resolve to the same guest identity.
    """
    client_a = TestClient(app)
    client_b = TestClient(app)

    identity_a = client_a.get(IDENTITY_URL).json()
    identity_b = client_b.get(IDENTITY_URL).json()

    assert identity_a["id"] != identity_b["id"]

    # And each stays itself on a second request -- isolation, not just
    # a one-off coincidence of the first response.
    assert client_a.get(IDENTITY_URL).json()["id"] == identity_a["id"]
    assert client_b.get(IDENTITY_URL).json()["id"] == identity_b["id"]


# --- Invalid/expired session handling ------------------------------------


def test_garbage_cookie_value_is_handled_safely_not_as_a_crash():
    """
    A cookie that doesn't correspond to any real session (e.g. forged,
    or left over from a wiped dev database) must not 500 -- it should
    be treated the same as having no session at all, and a fresh guest
    identity issued.
    """
    client = TestClient(app)
    client.cookies.set(settings.guest_session_cookie_name, "not-a-real-session-token")

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "guest"
    assert body["id"] != "not-a-real-session-token"


def test_expired_guest_session_no_longer_resolves_to_the_same_identity():
    client = TestClient(app)
    original = client.get(IDENTITY_URL).json()

    _backdate_last_seen(original["id"], minutes_ago=settings.guest_session_inactivity_minutes + 1)

    refreshed = client.get(IDENTITY_URL).json()

    assert refreshed["id"] != original["id"]


def test_expired_session_row_is_cleaned_up_when_next_encountered():
    client = TestClient(app)
    original = client.get(IDENTITY_URL).json()
    _backdate_last_seen(original["id"], minutes_ago=settings.guest_session_inactivity_minutes + 1)

    client.get(IDENTITY_URL)

    db = SessionLocal()
    try:
        stale_row = db.query(GuestSession).filter(GuestSession.id == original["id"]).first()
        assert stale_row is None
    finally:
        db.close()


# --- Activity / expiry interaction ---------------------------------------


def test_activity_within_the_window_keeps_the_same_identity_alive():
    """
    A session that's been quiet for a while, but not past the
    inactivity window, is still the same identity -- and touching it
    (this request) slides its expiry forward.
    """
    client = TestClient(app)
    original = client.get(IDENTITY_URL).json()

    # Comfortably inside the window, not past it.
    _backdate_last_seen(original["id"], minutes_ago=settings.guest_session_inactivity_minutes - 5)

    still_alive = client.get(IDENTITY_URL).json()
    assert still_alive["id"] == original["id"]

    # The request above should have slid last_seen_at back to "now",
    # not left it at the backdated value.
    db = SessionLocal()
    try:
        session = db.query(GuestSession).filter(GuestSession.id == original["id"]).first()
        naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert session.last_seen_at > naive_now - timedelta(minutes=1)
    finally:
        db.close()


# --- Service-level: exercised directly for expiration precision ---------


def test_service_get_valid_guest_session_returns_none_for_unknown_token():
    db = SessionLocal()
    try:
        assert guest_session_service.get_valid_guest_session(db, "does-not-exist") is None
    finally:
        db.close()


def test_service_get_valid_guest_session_returns_none_for_empty_token():
    db = SessionLocal()
    try:
        assert guest_session_service.get_valid_guest_session(db, "") is None
    finally:
        db.close()


def test_service_create_guest_session_returns_a_persisted_session():
    db = SessionLocal()
    try:
        session = guest_session_service.create_guest_session(db)

        assert session.id
        fetched = guest_session_service.get_valid_guest_session(db, session.id)
        assert fetched is not None
        assert fetched.id == session.id
    finally:
        db.close()


def test_service_two_created_sessions_have_different_tokens():
    db = SessionLocal()
    try:
        first = guest_session_service.create_guest_session(db)
        second = guest_session_service.create_guest_session(db)

        assert first.id != second.id
    finally:
        db.close()


def test_service_get_valid_guest_session_rejects_an_expired_session():
    db = SessionLocal()
    try:
        session = guest_session_service.create_guest_session(db)
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(
            minutes=settings.guest_session_inactivity_minutes + 1
        )
        db.commit()

        assert guest_session_service.get_valid_guest_session(db, session.id) is None
    finally:
        db.close()


def test_service_touch_guest_session_slides_expiry_forward():
    db = SessionLocal()
    try:
        session = guest_session_service.create_guest_session(db)
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(
            minutes=settings.guest_session_inactivity_minutes - 1
        )
        db.commit()

        guest_session_service.touch_guest_session(db, session)

        refreshed = guest_session_service.get_valid_guest_session(db, session.id)
        assert refreshed is not None
        assert refreshed.id == session.id
    finally:
        db.close()


def test_service_delete_guest_session_removes_the_row():
    db = SessionLocal()
    try:
        session = guest_session_service.create_guest_session(db)
        session_id = session.id

        guest_session_service.delete_guest_session(db, session_id)

        assert db.query(GuestSession).filter(GuestSession.id == session_id).first() is None
    finally:
        db.close()
