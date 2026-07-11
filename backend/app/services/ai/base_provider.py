from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """
    Raised when an AI provider fails to produce a response — bad API
    key, rate limit, network error, empty response, whatever. Callers
    (routes, services) catch this ONE exception type and never need to
    know or care which underlying provider or SDK raised it.
    """


class AIProvider(ABC):
    """
    The contract every provider (Gemini, and later OpenAI/Claude/Ollama)
    implements. Deliberately minimal: one method, prompt in, text out.

    Feature-specific concerns — how to phrase a summarization prompt,
    how to parse structured flashcard data — do NOT belong here. They
    belong in the service that calls this (e.g. summary_service.py).
    That split is what lets every future AI feature reuse this same
    interface unchanged.
    """

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Sends a prompt to the model and returns its text response."""
