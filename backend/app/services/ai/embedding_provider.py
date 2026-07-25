from abc import ABC, abstractmethod

# Reused rather than redefined: routes and services that fail while
# talking to an embedding model want to be handled exactly like ones
# that fail while talking to a text-generation model (bad key, rate
# limit, network error, empty response -> 502). One exception type for
# "an AI provider of any kind failed" keeps that handling in one place
# instead of forking it per capability.
from app.services.ai.base_provider import AIProviderError  # noqa: F401


class EmbeddingProvider(ABC):
    """
    The contract every embedding provider (Gemini today, others later)
    implements. This is a sibling of AIProvider, not a replacement or
    an extension of it — AIProvider's job is "prompt in, text out";
    this one's job is "text in, vector out". They're different
    capabilities with different failure modes and different callers,
    so keeping them as two small interfaces means a provider can
    implement either one, both, or swap one independently of the
    other, and AIProvider itself never has to change to accommodate
    retrieval.

    Two methods, not one, because embedding is asymmetric in RAG: the
    chunks you store and the query you search with play different
    roles, and some models (Gemini included) noticeably improve
    retrieval quality when told which is which. A provider that has no
    such distinction can simply implement both methods the same way —
    but a provider that can't offer the option isn't a choice this
    interface should make for every provider that can.
    """

    @abstractmethod
    async def embed_document(self, text: str) -> list[float]:
        """Embeds a piece of text that will be stored and searched over."""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embeds a search query, to be compared against stored embeddings."""
