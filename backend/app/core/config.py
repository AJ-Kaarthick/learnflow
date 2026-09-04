from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed application settings.

    Every value here can be overridden by an environment variable of the
    same name (case-insensitive), which pydantic-settings reads from a
    .env file automatically. This means secrets (like API keys) never
    get hardcoded into the source code, so they never end up on GitHub.
    """

    app_env: str = "development"
    database_url: str = "sqlite:///./learnflow.db"

    # Which AI provider to use. The factory in services/ai/provider_factory.py
    # reads this to decide which provider class to instantiate.
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    # Google regularly retires older Gemini model IDs — this exact
    # error (a working model suddenly 404ing) will happen again. When
    # it does: check https://ai.google.dev/gemini-api/docs/models for
    # the current lineup, or call provider.list_models() (see note in
    # gemini_provider.py) to see what your specific key can access.
    gemini_model: str = "gemini-3.1-flash-lite"

    # Separate from gemini_model because embedding models and text
    # generation models are different product lines that version on
    # their own schedules — Gemini has shipped many generations of
    # chat models against a single stable embedding model. See
    # gemini_embedding_provider.py for how this is used.
    gemini_embedding_model: str = "gemini-embedding-001"

    # Which OCR engine to use for scanned PDFs and images. The factory
    # in services/ocr/ocr_engine_factory.py reads this to decide which
    # engine class to instantiate — same "typed setting picks a class
    # out of a small registry" pattern as ai_provider above.
    ocr_engine: str = "tesseract"

    # The frontend's origin, used to configure CORS below.
    frontend_origin: str = "http://localhost:5173"

    # V3 Milestone 1 Phase 1: guest identity/session foundation (see
    # app/api/deps.py and app/services/guest_session_service.py).
    #
    # How long a guest session stays valid with no activity before
    # it's treated as expired. 30-60 minutes is a reasonable range for
    # a study session someone might step away from briefly; 45 splits
    # the difference. Sliding: any request that resolves to a session
    # bumps its clock back to zero (see
    # guest_session_service.touch_guest_session), so this is "minutes
    # since last activity", not "minutes since the session started".
    guest_session_inactivity_minutes: int = 45

    # The cookie name the guest session token is stored under. Kept
    # configurable (rather than a bare string literal at each call
    # site) for the same reason every other cross-cutting value in
    # this file is a setting -- one place to change it, e.g. if a
    # later environment needs to namespace it further.
    guest_session_cookie_name: str = "learnflow_guest_session"

    # Whether the guest session cookie requires HTTPS to be sent.
    # False by default so local development (plain http://localhost)
    # keeps working with zero setup, matching this file's existing
    # "safe default value consistent with the existing configuration
    # architecture" convention. Should be set True (via the
    # GUEST_SESSION_COOKIE_SECURE env var) in any real deployment --
    # see the `samesite` setting below, which forces this in practice
    # once frontend and backend are on different sites.
    guest_session_cookie_secure: bool = False

    # "lax" is correct for local dev, where the frontend
    # (localhost:5173) and backend (localhost:8000) are different
    # origins but the same *site* (SameSite is computed from the
    # registrable domain, not the full origin, and "localhost" has
    # none to register) -- Lax cookies are still sent on these
    # cross-origin, same-site requests. A production deployment on two
    # genuinely different domains is cross-*site*, which needs "none"
    # here -- and per the cookie spec, SameSite=None is only honored
    # by browsers when `Secure` is also set, so
    # guest_session_cookie_secure must be switched to True alongside
    # this.
    guest_session_cookie_samesite: str = "lax"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# A single shared instance. Other modules import `settings` from here
# rather than constructing their own Settings() — that way the .env
# file is only read once, and every part of the app sees the same values.
settings = Settings()
