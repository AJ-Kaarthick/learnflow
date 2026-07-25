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

    # The frontend's origin, used to configure CORS below.
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# A single shared instance. Other modules import `settings` from here
# rather than constructing their own Settings() — that way the .env
# file is only read once, and every part of the app sees the same values.
settings = Settings()
