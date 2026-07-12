from sqlalchemy.orm import Session

from app.db.models import Document, Flashcard
from app.services.ai.base_provider import AIProvider
from app.services.ai.structured_output import parse_json_array

MAX_CHARACTERS_FOR_PROMPT = 15000
DEFAULT_FLASHCARD_COUNT = 10


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
    cards_data = parse_json_array(raw_text, required_keys={"question", "answer"})

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
