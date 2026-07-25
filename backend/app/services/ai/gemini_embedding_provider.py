from google import genai
from google.genai import types

from app.core.config import settings
from app.services.ai.base_provider import AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Talks to Google's Gemini embedding model via the same google-genai
    SDK GeminiProvider (see gemini_provider.py) uses for text
    generation — same client library, different model and endpoint.

    Important difference from GeminiProvider.generate_text: Gemini's
    embedding endpoint accepts exactly one input text per request (no
    batching multiple chunks into one call the way you might expect
    from generate_content). embedding_service.py calls this once per
    chunk for that reason — see the comment there.
    """

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            # Same reasoning as GeminiProvider: a missing API key is a
            # setup problem for the developer to fix, not a transient
            # AI failure, so it's a RuntimeError rather than an
            # AIProviderError.
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to backend/.env "
                "(see backend/.env.example)."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_embedding_model

    async def _embed(self, text: str, task_type: str) -> list[float]:
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type),
            )
        except Exception as error:
            raise AIProviderError(f"Gemini embedding request failed: {error}") from error

        if not response.embeddings:
            raise AIProviderError("Gemini returned no embedding.")

        return list(response.embeddings[0].values)

    async def embed_document(self, text: str) -> list[float]:
        # RETRIEVAL_DOCUMENT tells Gemini this text is something that
        # will be *searched over*, which is what asymmetric embedding
        # means in practice: this and RETRIEVAL_QUERY below produce
        # vectors optimized to be compared against each other, not
        # necessarily against more vectors of their own task_type.
        return await self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        # RETRIEVAL_QUERY tells Gemini this text is a search question,
        # not stored content — the counterpart to embed_document above.
        return await self._embed(text, task_type="RETRIEVAL_QUERY")
