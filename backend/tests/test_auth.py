"""
V3 Milestone 1 Phase 2: account authentication.

Covers signup/signin/logout through the HTTP layer (POST
/api/v1/auth/...), the extended identity resolution in
app/api/deps.py:get_current_identity (authenticated sessions winning
over guest resolution, and falling back to it correctly), and
auth_service.py's password hashing/verification at the service level
-- same "HTTP-level behavior plus service-level precision" split as
test_identity_session.py, which this file deliberately does not
modify (Phase 1's guest-only behavior is exercised there and must keep
passing unchanged).
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import User, UserSession
from app.main import app
from app.services import auth_service, user_session_service

IDENTITY_URL = "/api/v1/identity/me"
SIGNUP_URL = "/api/v1/auth/signup"
SIGNIN_URL = "/api/v1/auth/signin"
LOGOUT_URL = "/api/v1/auth/logout"

# Satisfies the password policy added after manual QA on the first
# Phase 2 pass (schemas/auth.py:_validate_password_strength): 8+
# characters, upper, lower, digit, special. Used everywhere a test
# needs signup/signin to actually *succeed* -- tests exercising the
# policy itself (below) use their own deliberately-non-compliant
# passwords instead.
VALID_PASSWORD = "Correct-Horse1!"


def _unique_email(label: str) -> str:
    # Each test gets its own email so tests never collide with each
    # other's rows in the shared per-session test database (see
    # conftest.py) -- mirrors how other test files in this suite pick
    # distinct ids/filenames per test.
    return f"{label}.{datetime.now(timezone.utc).timestamp()}@example.com"


def _backdate_last_seen(session_id: str, days_ago: float) -> None:
    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.commit()
    finally:
        db.close()


# --- Signup ---------------------------------------------------------------


def test_signup_creates_an_account_and_signs_in():
    client = TestClient(app)
    email = _unique_email("newuser")

    response = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "user"
    assert body["email"] == email
    assert body["id"]
    # An authenticated session cookie was issued -- what lets the next
    # request from this browser resolve back to this same account.
    assert settings.user_session_cookie_name in response.cookies


def test_signup_normalizes_email_case_and_whitespace():
    client = TestClient(app)
    raw_email = f"  MixedCase.{datetime.now(timezone.utc).timestamp()}@Example.COM  "

    response = client.post(SIGNUP_URL, json={"email": raw_email, "password": VALID_PASSWORD})

    assert response.status_code == 201
    assert response.json()["email"] == raw_email.strip().lower()


def test_duplicate_signup_is_rejected():
    client = TestClient(app)
    email = _unique_email("dupe")

    first = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    assert first.status_code == 201

    second = client.post(SIGNUP_URL, json={"email": email, "password": "Different-Pass2#"})
    assert second.status_code == 409


def test_duplicate_signup_is_rejected_regardless_of_email_case():
    client = TestClient(app)
    email = _unique_email("caseinsensitive")

    first = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    assert first.status_code == 201

    second = client.post(SIGNUP_URL, json={"email": email.upper(), "password": VALID_PASSWORD})
    assert second.status_code == 409


def test_signup_rejects_malformed_email():
    client = TestClient(app)

    response = client.post(SIGNUP_URL, json={"email": "not-an-email", "password": VALID_PASSWORD})

    assert response.status_code == 422


def test_signup_rejects_email_missing_a_domain_suffix():
    """
    Manual QA on the first Phase 2 pass found that inputs like
    "test@gmail" and "oidu@text" -- syntactically email-shaped (one
    `@`, something on both sides) but missing a domain suffix
    entirely -- were getting further than they should. Covered here
    as its own regression test, distinct from
    test_signup_rejects_malformed_email's more obviously-broken input.
    """
    client = TestClient(app)

    for email in ["test@gmail", "oidu@text"]:
        response = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
        assert response.status_code == 422, f"expected {email!r} to be rejected"
        assert response.json()["detail"][0]["msg"].endswith("Please enter a valid email address.")


def test_signup_accepts_a_syntactically_valid_email():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("validshape"), "password": VALID_PASSWORD}
    )

    assert response.status_code == 201


# --- Password policy ---------------------------------------------------


def test_signup_accepts_a_password_meeting_every_requirement():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("goodpw"), "password": "Password1!"}
    )

    assert response.status_code == 201


def test_signup_rejects_password_that_is_too_short():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("shortpw"), "password": "Sh0rt!"}
    )

    assert response.status_code == 422


def test_signup_rejects_password_missing_an_uppercase_letter():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("noupper"), "password": "lowercase1!"}
    )

    assert response.status_code == 422


def test_signup_rejects_password_missing_a_lowercase_letter():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("nolower"), "password": "UPPERCASE1!"}
    )

    assert response.status_code == 422


def test_signup_rejects_password_missing_a_number():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("nonumber"), "password": "NoNumberHere!"}
    )

    assert response.status_code == 422


def test_signup_rejects_password_missing_a_special_character():
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("nospecial"), "password": "NoSpecial123"}
    )

    assert response.status_code == 422


def test_signup_rejects_a_password_that_is_only_digits():
    """The exact case manual QA flagged: "11111111" -- 8 characters, meets the length floor, meets nothing else."""
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("onlydigits"), "password": "11111111"}
    )

    assert response.status_code == 422


def test_password_policy_rejection_gives_a_human_readable_message_not_a_raw_object():
    """
    Manual QA on the first Phase 2 pass found the frontend rendering
    "[object Object]" for a validation failure -- traced to FastAPI's
    `detail` being a list of structured error objects, not a plain
    string, for a 422. This test doesn't cover the frontend directly
    (see frontend/src/api/auth.test.js for that), but it does pin down
    the *backend* half of that contract: the message text itself must
    be a plain, human-readable sentence, so any client unwrapping
    `detail[i].msg` gets something presentable.
    """
    client = TestClient(app)

    response = client.post(
        SIGNUP_URL, json={"email": _unique_email("readablemsg"), "password": "11111111"}
    )

    detail = response.json()["detail"]
    assert isinstance(detail, list)
    message = detail[0]["msg"]
    assert "[object Object]" not in message
    assert message.endswith(
        "Password must be at least 8 characters and include an uppercase letter, "
        "a lowercase letter, a number, and a special character."
    )


def test_password_is_stored_as_a_secure_hash_not_plaintext():
    client = TestClient(app)
    email = _unique_email("hashcheck")
    password = VALID_PASSWORD

    response = client.post(SIGNUP_URL, json={"email": email, "password": password})
    assert response.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        # Never the plaintext password itself...
        assert user.password_hash != password
        assert password not in user.password_hash
        # ...and recognizably a bcrypt hash, not some ad-hoc encoding.
        assert user.password_hash.startswith("$2")
    finally:
        db.close()


# --- Signin -----------------------------------------------------------------


def test_signin_with_correct_credentials_succeeds():
    client = TestClient(app)
    email = _unique_email("signinok")
    password = VALID_PASSWORD
    client.post(SIGNUP_URL, json={"email": email, "password": password})
    client.cookies.clear()

    response = client.post(SIGNIN_URL, json={"email": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "user"
    assert body["email"] == email
    assert settings.user_session_cookie_name in response.cookies


def test_signin_with_wrong_password_is_rejected():
    client = TestClient(app)
    email = _unique_email("wrongpw")
    client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    client.cookies.clear()

    response = client.post(SIGNIN_URL, json={"email": email, "password": "totally-wrong"})

    assert response.status_code == 401
    assert settings.user_session_cookie_name not in response.cookies


def test_signin_with_unknown_email_is_rejected():
    client = TestClient(app)

    response = client.post(
        SIGNIN_URL, json={"email": _unique_email("neverexisted"), "password": "whatever123"}
    )

    assert response.status_code == 401


def test_signin_failure_responses_do_not_reveal_whether_the_account_exists():
    """
    Security requirement: "avoid unnecessarily revealing whether an
    account exists". A wrong password for a real account and a login
    attempt against an email that was never registered must be
    indistinguishable from the response alone.
    """
    client = TestClient(app)
    real_email = _unique_email("realaccount")
    client.post(SIGNUP_URL, json={"email": real_email, "password": VALID_PASSWORD})
    client.cookies.clear()

    wrong_password_response = client.post(
        SIGNIN_URL, json={"email": real_email, "password": "not-the-password"}
    )
    unknown_email_response = client.post(
        SIGNIN_URL, json={"email": _unique_email("neverexisted2"), "password": "not-the-password"}
    )

    assert wrong_password_response.status_code == unknown_email_response.status_code == 401
    assert wrong_password_response.json()["detail"] == unknown_email_response.json()["detail"]


# --- Authenticated identity resolution --------------------------------------


def test_authenticated_identity_resolves_via_identity_me():
    client = TestClient(app)
    email = _unique_email("resolveme")
    signup_response = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    user_id = signup_response.json()["id"]

    identity = client.get(IDENTITY_URL).json()

    assert identity["type"] == "user"
    assert identity["id"] == user_id
    assert identity["email"] == email


def test_authenticated_session_persists_across_multiple_requests():
    client = TestClient(app)
    email = _unique_email("persist")
    client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})

    first = client.get(IDENTITY_URL).json()
    second = client.get(IDENTITY_URL).json()

    assert first["type"] == second["type"] == "user"
    assert first["id"] == second["id"]


def test_authenticated_session_takes_priority_over_a_stale_guest_cookie():
    """
    A browser that used the app as a guest before signing up/in still
    carries its old guest-session cookie afterward (Phase 2 doesn't
    touch it -- migration is out of scope). Once a valid authenticated
    session cookie is also present, it must be what resolves, not the
    leftover guest one.
    """
    client = TestClient(app)
    guest_identity = client.get(IDENTITY_URL).json()
    assert guest_identity["type"] == "guest"

    email = _unique_email("prioritycheck")
    client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})

    identity_after_signup = client.get(IDENTITY_URL).json()
    assert identity_after_signup["type"] == "user"
    assert identity_after_signup["id"] != guest_identity["id"]


def test_two_different_accounts_never_resolve_to_the_same_identity():
    client_a = TestClient(app)
    client_b = TestClient(app)
    email_a = _unique_email("usera")
    email_b = _unique_email("userb")

    client_a.post(SIGNUP_URL, json={"email": email_a, "password": VALID_PASSWORD})
    client_b.post(SIGNUP_URL, json={"email": email_b, "password": VALID_PASSWORD})

    identity_a = client_a.get(IDENTITY_URL).json()
    identity_b = client_b.get(IDENTITY_URL).json()

    assert identity_a["id"] != identity_b["id"]
    assert identity_a["email"] != identity_b["email"]


def test_garbage_user_session_cookie_falls_back_to_guest_not_a_crash():
    client = TestClient(app)
    client.cookies.set(settings.user_session_cookie_name, "not-a-real-session-token")

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200
    assert response.json()["type"] == "guest"


def test_expired_authenticated_session_falls_back_to_guest():
    client = TestClient(app)
    email = _unique_email("expiring")
    signup_response = client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    user_session_token = signup_response.cookies[settings.user_session_cookie_name]

    _backdate_last_seen(
        user_session_token, days_ago=settings.user_session_inactivity_days + 1
    )

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200
    assert response.json()["type"] == "guest"


# --- Logout -------------------------------------------------------------


def test_logout_invalidates_the_authenticated_session():
    client = TestClient(app)
    email = _unique_email("logout")
    client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})
    assert client.get(IDENTITY_URL).json()["type"] == "user"

    logout_response = client.post(LOGOUT_URL)
    assert logout_response.status_code == 204

    identity_after = client.get(IDENTITY_URL).json()
    assert identity_after["type"] == "guest"


def test_logout_is_safe_to_call_without_an_active_session():
    client = TestClient(app)

    response = client.post(LOGOUT_URL)

    assert response.status_code == 204


def test_logout_does_not_disturb_guest_session_infrastructure():
    """Per the brief: logout must not destroy unrelated guest-session infrastructure."""
    client = TestClient(app)
    email = _unique_email("logoutguest")
    client.post(SIGNUP_URL, json={"email": email, "password": VALID_PASSWORD})

    client.post(LOGOUT_URL)

    # After logout, the very next identity resolution is allowed to
    # mint a fresh guest session (Phase 2 doesn't preserve a
    # pre-signup guest identity across the auth flow) -- the point of
    # this test is only that it works normally, with no error and a
    # real guest identity, exactly like a browser that was never
    # signed in.
    identity = client.get(IDENTITY_URL).json()
    assert identity["type"] == "guest"
    assert identity["id"]


# --- Regression: guest identity/session behavior is unaffected -------------


def test_guest_identity_still_works_when_never_authenticating():
    client = TestClient(app)

    response = client.get(IDENTITY_URL)

    assert response.status_code == 200
    assert response.json()["type"] == "guest"


def test_unauthenticated_requests_to_other_routes_are_still_treated_as_guest():
    client = TestClient(app)

    documents_response = client.get("/api/v1/documents")
    identity = client.get(IDENTITY_URL).json()

    assert documents_response.status_code == 200
    assert identity["type"] == "guest"


# --- Service-level: auth_service ---------------------------------------


def test_service_hash_password_never_returns_the_plaintext():
    hashed = auth_service.hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert hashed.startswith("$2")


def test_service_verify_password_accepts_the_right_password():
    hashed = auth_service.hash_password("correct-horse-battery-staple")
    assert auth_service.verify_password("correct-horse-battery-staple", hashed) is True


def test_service_verify_password_rejects_the_wrong_password():
    hashed = auth_service.hash_password("correct-horse-battery-staple")
    assert auth_service.verify_password("wrong-password", hashed) is False


def test_service_verify_password_returns_false_not_an_exception_for_a_corrupt_hash():
    assert auth_service.verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_service_two_hashes_of_the_same_password_are_different():
    # Per-call random salt (bcrypt.gensalt()) -- guards against two
    # users who pick the same password ending up with identical rows.
    first = auth_service.hash_password("correct-horse-battery-staple")
    second = auth_service.hash_password("correct-horse-battery-staple")
    assert first != second
    assert auth_service.verify_password("correct-horse-battery-staple", first) is True
    assert auth_service.verify_password("correct-horse-battery-staple", second) is True


def test_service_create_user_persists_a_normalized_lowercase_email():
    db = SessionLocal()
    try:
        email = f"  Service.{datetime.now(timezone.utc).timestamp()}@EXAMPLE.com  "
        user = auth_service.create_user(db, email, "correct-horse-battery-staple")
        assert user.email == email.strip().lower()
    finally:
        db.close()


def test_service_create_user_raises_on_duplicate_email():
    db = SessionLocal()
    try:
        email = f"serviceDupe.{datetime.now(timezone.utc).timestamp()}@example.com"
        auth_service.create_user(db, email, "correct-horse-battery-staple")

        try:
            auth_service.create_user(db, email, "a-different-password")
            assert False, "expected EmailAlreadyRegisteredError"
        except auth_service.EmailAlreadyRegisteredError:
            pass
    finally:
        db.close()


def test_service_authenticate_user_returns_none_for_unknown_email():
    db = SessionLocal()
    try:
        assert auth_service.authenticate_user(db, "no-such-account@example.com", "whatever") is None
    finally:
        db.close()


# --- Service-level: user_session_service --------------------------------


def test_service_get_valid_user_session_returns_none_for_unknown_token():
    db = SessionLocal()
    try:
        assert user_session_service.get_valid_user_session(db, "does-not-exist") is None
    finally:
        db.close()


def test_service_create_user_session_returns_a_persisted_session():
    db = SessionLocal()
    try:
        user = auth_service.create_user(
            db, _unique_email("sessionsvc"), "correct-horse-battery-staple"
        )
        session = user_session_service.create_user_session(db, user.id)

        assert session.id
        fetched = user_session_service.get_valid_user_session(db, session.id)
        assert fetched is not None
        assert fetched.user_id == user.id
    finally:
        db.close()


def test_service_get_valid_user_session_rejects_an_expired_session():
    db = SessionLocal()
    try:
        user = auth_service.create_user(
            db, _unique_email("expiredsvc"), "correct-horse-battery-staple"
        )
        session = user_session_service.create_user_session(db, user.id)
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(
            days=settings.user_session_inactivity_days + 1
        )
        db.commit()

        assert user_session_service.get_valid_user_session(db, session.id) is None
    finally:
        db.close()


def test_service_touch_user_session_slides_expiry_forward():
    db = SessionLocal()
    try:
        user = auth_service.create_user(
            db, _unique_email("touchsvc"), "correct-horse-battery-staple"
        )
        session = user_session_service.create_user_session(db, user.id)
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(
            days=settings.user_session_inactivity_days - 1
        )
        db.commit()

        user_session_service.touch_user_session(db, session)

        refreshed = user_session_service.get_valid_user_session(db, session.id)
        assert refreshed is not None
    finally:
        db.close()


def test_service_delete_user_session_removes_the_row():
    db = SessionLocal()
    try:
        user = auth_service.create_user(
            db, _unique_email("deletesvc"), "correct-horse-battery-staple"
        )
        session = user_session_service.create_user_session(db, user.id)
        session_id = session.id

        user_session_service.delete_user_session(db, session_id)

        assert db.query(UserSession).filter(UserSession.id == session_id).first() is None
    finally:
        db.close()
