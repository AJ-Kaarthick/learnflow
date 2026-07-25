"""
Turns a document's extracted text into searchable DocumentChunk rows:
split -> embed -> store. This is the "write path" of the RAG
foundation; retrieval_service.py is the "read path" that queries what
this writes.

Kept as its own service, separate from any single feature, because
indexing isn't specific to chat, tutor mode, or any other future
feature — it's a shared prerequisite all of them need, the same way
pdf_service.extract_text() is a shared prerequisite for summary, quiz,
flashcards, and mind map today.

A note on changing GEMINI_EMBEDDING_MODEL later: different embedding
models produce vectors of different lengths and in different
"directions" for the same text, so comparing a query embedded with a
new model against chunks embedded with an old one produces meaningless
similarity scores. This module has no way to detect that a document's
existing chunks came from a since-replaced model — the `existing`
check above only asks "does this document have chunks at all," not
"were they made with the current model." Swapping embedding models is
therefore not a config-only change: every already-indexed document's
DocumentChunk rows need to be deleted so this function re-embeds them
from scratch. There's no data migration for this in V2 Milestone 1 —
it's flagged as a known limitation, since nothing in this milestone
lets the model be changed without a manual DB cleanup step.
"""

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.rag.chunking import chunk_text


async def index_document(
    document: Document, db: Session, embedding_provider: EmbeddingProvider
) -> list[DocumentChunk]:
    """
    Returns this document's existing chunks if it's already been
    indexed (same "generate once, reuse forever" caching pattern as
    generate_summary_for_document and friends — avoids re-embedding,
    and therefore re-paying for, unchanged text on every call).
    Otherwise chunks the document's extracted text, embeds every
    chunk, saves the results, and returns them.

    Returns an empty list (rather than raising) for a document with no
    extracted text — nothing to index isn't an error, it's just an
    empty result, the same way a summary of an empty document would be
    a weak summary, not a crash.
    """
    existing = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    if existing:
        return existing

    pieces = chunk_text(document.extracted_text or "")
    if not pieces:
        return []

    # One embedding request per chunk, not one batched request for all
    # of them: unlike generate_text, Gemini's embedding endpoint only
    # accepts a single input text per call (see the note in
    # GeminiEmbeddingProvider). A concurrent version of this loop
    # (asyncio.gather, with a concurrency cap to stay under rate
    # limits) would index a large document faster — worth doing if
    # indexing latency becomes a real problem, but indexing a document
    # is a rare, one-time-per-document event, so the simpler
    # sequential version is the right starting point.
    chunks: list[DocumentChunk] = []
    for index, piece in enumerate(pieces):
        embedding = await embedding_provider.embed_document(piece)
        chunks.append(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=piece,
                embedding=embedding,
            )
        )

    db.add_all(chunks)
    db.commit()
    for chunk in chunks:
        db.refresh(chunk)
    return chunks
