from sqlalchemy.orm import Session

from app.db.models import Document, Summary
from app.services.ai.base_provider import AIProvider

# Keeps the prompt (and therefore cost and latency) bounded for very
# long documents. Revisit if V2's chat feature needs the full text
# handled differently (that's a chunking problem, not a truncation one).
MAX_CHARACTERS_FOR_PROMPT = 15000


def build_summary_prompt(document_text: str) -> str:
    truncated = document_text[:MAX_CHARACTERS_FOR_PROMPT]
    return (
        "Summarize the following document for a student who is studying "
        "it. Use clear, plain language and structure the summary as a "
        "short list of the key points.\n\n"
        f"Document:\n{truncated}"
    )


async def generate_summary_for_document(
    document: Document, db: Session, provider: AIProvider
) -> Summary:
    """
    Returns an existing summary if one was already generated for this
    document (avoids burning API quota on repeat requests), otherwise
    generates and saves a new one.
    """
    existing = db.query(Summary).filter(Summary.document_id == document.id).first()
    if existing is not None:
        return existing

    prompt = build_summary_prompt(document.extracted_text or "")
    content = await provider.generate_text(prompt)

    summary = Summary(document_id=document.id, content=content)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary
