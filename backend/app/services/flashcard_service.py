import json
import re

from sqlalchemy.orm import Session

from app.db.models import Document, Flashcard
from app.services.ai.base_provider import AIProvider, AIProviderError

MAX_CHARACTERS_FOR_PROMPT = 15000
DEFAULT_FLASHCARD_COUNT = 10

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$")


def build_flashcard_prompt(document_text: str, count: int) -> str:
    truncated = document_text[:MAX_CHARACTERS_FOR_PROMPT]
    return (
        f"Create exactly {count} flashcards for a student studying the "
        "document below. Each flashcard should test one distinct concept "
        "with a clear question and a concise answer.\n\n"
        "Respond with ONLY a JSON array — no markdown code fences, no "
        "commentary before or after it. Each item must look exactly like "
        'this: {"question": "...", "answer": "..."}\n\n'
        f"Document:\n{truncated}"
    )


def _parse_flashcards_json(raw_text: str) -> list[dict]:
    """
    Models occasionally ignore "no markdown fences" and wrap the JSON
    in ```json ... ``` anyway, or add a sentence before/after it. This
    strips the common case and raises a clear AIProviderError if the
    result still isn't usable — a bad response from the AI is treated
    as the same category of failure as the AI being unreachable, since
    from the caller's side both mean "no usable result, try again."
    """
    cleaned = _CODE_FENCE_PATTERN.sub("", raw_text.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise AIProviderError(
            f"Gemini did not return valid JSON for flashcards: {error}"
        ) from error

    if not isinstance(data, list):
        raise AIProviderError("Expected a JSON array of flashcards.")

    for item in data:
        if not isinstance(item, dict) or "question" not in item or "answer" not in item:
            raise AIProviderError("Each flashcard must have a 'question' and 'answer'.")

    return data


async def generate_flashcards_for_document(
    document: Document,
    db: Session,
    provider: AIProvider,
    count: int = DEFAULT_FLASHCARD_COUNT,
) -> list[Flashcard]:
    """
    Returns existing flashcards for this document if any were already
    generated (same repeat-request cost/consistency rationale as
    summaries — but more important here, since flashcards need to stay
    stable across study sessions), otherwise generates and saves a new set.
    """
    existing = (
        db.query(Flashcard)
        .filter(Flashcard.document_id == document.id)
        .order_by(Flashcard.position)
        .all()
    )
    if existing:
        return existing

    prompt = build_flashcard_prompt(document.extracted_text or "", count)
    raw_text = await provider.generate_text(prompt)
    cards_data = _parse_flashcards_json(raw_text)

    flashcards = [
        Flashcard(
            document_id=document.id,
            question=card["question"],
            answer=card["answer"],
            position=index,
        )
        for index, card in enumerate(cards_data)
    ]
    db.add_all(flashcards)
    db.commit()
    for card in flashcards:
        db.refresh(card)
    return flashcards
