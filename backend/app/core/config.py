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

    # Which AI provider to use. Milestone 2 will read this to decide
    # whether to instantiate the OpenAI, Gemini, or Claude implementation.
    ai_provider: str = "gemini"
    gemini_api_key: str = ""

    # The frontend's origin, used to configure CORS below.
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# A single shared instance. Other modules import `settings` from here
# rather than constructing their own Settings() — that way the .env
# file is only read once, and every part of the app sees the same values.
settings = Settings()
