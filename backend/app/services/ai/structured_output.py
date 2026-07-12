import json
import re
from typing import Any

from app.services.ai.base_provider import AIProviderError

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$")


def extract_json(raw_text: str) -> Any:
    """
    Strips markdown code fences a model might add despite being told
    not to, then parses the result as JSON — array, object, whatever
    comes out. Raises AIProviderError (never a raw JSONDecodeError) so
    every feature that asks for structured output can catch one
    exception type, the same one used for provider failures, without
    caring whether "no usable result" came from the network or from
    the model ignoring the format instructions.

    This is the shared primitive. Shape-specific checks (must be a
    list of these keys, must be a valid tree, ...) belong in the
    caller — see parse_json_array below for the list case, and
    mindmap_service.py for the tree case.
    """
    cleaned = _CODE_FENCE_PATTERN.sub("", raw_text.strip())

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise AIProviderError(f"AI response was not valid JSON: {error}") from error


def parse_json_array(raw_text: str, required_keys: set[str]) -> list[dict]:
    """
    Parses a JSON array of objects out of raw LLM text, used by
    features whose output is a flat list of similarly-shaped items
    (flashcards, quiz questions).
    """
    data = extract_json(raw_text)

    if not isinstance(data, list):
        raise AIProviderError("Expected a JSON array.")

    for item in data:
        if not isinstance(item, dict) or not required_keys.issubset(item):
            raise AIProviderError(f"Each item must include: {sorted(required_keys)}.")

    return data
