from google import genai

from app.core.config import settings
from app.services.ai.base_provider import AIProvider, AIProviderError


class GeminiProvider(AIProvider):
    """Talks to Google's Gemini API via the official google-genai SDK."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            # A misconfiguration (missing setup), not an AI failure —
            # deliberately NOT an AIProviderError, so it surfaces as a
            # clear 500 telling the developer what to fix, instead of
            # being treated like a transient upstream failure.
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to backend/.env "
                "(see backend/.env.example)."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    async def generate_text(self, prompt: str) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
            )
        except Exception as error:
            raise AIProviderError(f"Gemini request failed: {error}") from error

        if not response.text:
            raise AIProviderError("Gemini returned an empty response.")

        return response.text
