import json
import re

from app.services.ai.base_provider import AIProviderError

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_json_array(raw_text: str, required_keys: set[str]) -> list[dict]:
    """
    Parses a JSON array of objects out of raw LLM text.

    Models occasionally wrap JSON in markdown code fences or add a
    sentence before/after it despite being told not to — this strips
    the common case. Raises AIProviderError (never a raw JSON/parsing
    error) so every feature that asks for structured output — right
    now flashcards and quiz, and mind maps next — can catch the same
    one exception type used for provider failures, without knowing or
    caring whether "no usable result" came from the network or from
    the model ignoring the format instructions.
    """
    cleaned = _CODE_FENCE_PATTERN.sub("", raw_text.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise AIProviderError(f"AI response was not valid JSON: {error}") from error

    if not isinstance(data, list):
        raise AIProviderError("Expected a JSON array.")

    for item in data:
        if not isinstance(item, dict) or not required_keys.issubset(item):
            raise AIProviderError(f"Each item must include: {sorted(required_keys)}.")

    return data
