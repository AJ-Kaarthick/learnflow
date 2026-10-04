import json
import re
from typing import Any

from app.services.ai.base_provider import AIProviderError

_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_STRIP_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


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
    text = (raw_text or "").strip()
    if not text:
        raise AIProviderError("AI response was empty.")

    # 1. Attempt extracting from markdown code fence block if present
    fence_match = _CODE_BLOCK_PATTERN.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass

    # 2. Attempt legacy fence strip
    cleaned = _STRIP_FENCE_PATTERN.sub("", text).strip()
    try:
        return json.loads(cleaned, strict=False)
    except Exception:
        pass

    # 3. Attempt finding outermost JSON object or array bounds
    first_brace = text.find("{")
    first_bracket = text.find("[")

    start_idx = -1
    end_idx = -1

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        last_brace = text.rfind("}")
        if last_brace > first_brace:
            start_idx = first_brace
            end_idx = last_brace + 1
    elif first_bracket != -1:
        last_bracket = text.rfind("]")
        if last_bracket > first_bracket:
            start_idx = first_bracket
            end_idx = last_bracket + 1

    if start_idx != -1 and end_idx != -1:
        slice_candidate = text[start_idx:end_idx].strip()
        try:
            return json.loads(slice_candidate, strict=False)
        except Exception:
            pass

    # 4. Final attempt with cleaned and capture JSONDecodeError
    try:
        return json.loads(cleaned, strict=False)
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
