from app.core.config import settings
from app.services.ai.base_provider import AIProvider
from app.services.ai.gemini_provider import GeminiProvider

# Adding OpenAI or Claude later means: write one class implementing
# AIProvider, add one line here. Nothing else in the codebase changes.
_PROVIDERS: dict[str, type[AIProvider]] = {
    "gemini": GeminiProvider,
}


def get_ai_provider() -> AIProvider:
    """
    FastAPI dependency that returns the configured AI provider.

    Using this via Depends() (see routes_summary.py) — rather than
    calling it as a plain function — is what lets tests substitute a
    fake provider with app.dependency_overrides, so the test suite
    never calls the real Gemini API.
    """
    provider_class = _PROVIDERS.get(settings.ai_provider)
    if provider_class is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}'. "
            f"Available: {list(_PROVIDERS)}"
        )
    return provider_class()
