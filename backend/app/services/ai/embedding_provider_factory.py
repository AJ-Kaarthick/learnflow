from app.core.config import settings
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.gemini_embedding_provider import GeminiEmbeddingProvider

# Deliberately keyed by the same settings.ai_provider value as
# _PROVIDERS in provider_factory.py, rather than introducing a second
# EMBEDDING_PROVIDER setting. In practice the two travel together — if
# LearnFlow switches from Gemini to OpenAI for text generation, it's
# switching AI vendors, and would want that vendor's embedding model
# too. Splitting them into two independent settings would let someone
# configure a combination that's never actually been exercised (e.g.
# Claude for text, Gemini for embeddings) for no real benefit today.
# If that combination is ever genuinely needed, this is the one place
# it would change.
_EMBEDDING_PROVIDERS: dict[str, type[EmbeddingProvider]] = {
    "gemini": GeminiEmbeddingProvider,
}


def get_embedding_provider() -> EmbeddingProvider:
    """
    FastAPI dependency that returns the configured embedding provider —
    the embedding-side counterpart to get_ai_provider() in
    provider_factory.py. Used the same way, via Depends(), so tests can
    substitute a fake embedding provider with app.dependency_overrides
    and never call the real Gemini API either.
    """
    provider_class = _EMBEDDING_PROVIDERS.get(settings.ai_provider)
    if provider_class is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}' for embeddings. "
            f"Available: {list(_EMBEDDING_PROVIDERS)}"
        )
    return provider_class()
