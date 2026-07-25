"""
The "read path" of the RAG foundation: given a document and a
natural-language query, returns the chunks most semantically similar
to that query.

This is deliberately the ONLY thing this file does. It doesn't build a
prompt, call an AIProvider for text generation, or know anything about
chat, tutor mode, or any other feature that will eventually consume
its output. That's what the architecture rule "future AI features
should depend on Retrieval, not the other way around" means in
practice: every future feature that needs "relevant context for this
question" calls retrieve_relevant_chunks() and decides for itself what
to do with the result (build a prompt, cite a source, whatever) —
retrieval never needs to know or care which of those callers is asking.
"""

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import DocumentChunk
from app.services.ai.embedding_provider import EmbeddingProvider

DEFAULT_TOP_K = 5


@dataclass
class ScoredChunk:
    """A DocumentChunk paired with how similar it is to a query (1.0 = most similar)."""

    chunk: DocumentChunk
    score: float


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Cosine similarity: the cosine of the angle between two vectors.
    1.0 means they point in the same direction (same meaning), 0.0
    means unrelated, -1.0 means opposite. This — not raw distance — is
    the standard similarity measure for text embeddings, because an
    embedding vector's *length* mostly reflects incidental factors
    like text length, while its *direction* is what encodes meaning;
    cosine similarity compares direction and ignores length.

    Implemented in plain Python rather than with a numerical library
    like numpy: at LearnFlow's scale (retrieval_relevant_chunks below
    loads at most a few hundred chunks per document into memory and
    compares each one once per query) a Python loop finishes in well
    under a millisecond per comparison — nowhere near slow enough to
    justify a new dependency. If retrieval ever needs to scan tens of
    thousands of chunks per query, that's the point where numpy's
    vectorized operations would start to matter, and this is the one
    function that would change to use them.
    """
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


async def retrieve_relevant_chunks(
    document_id: str,
    query: str,
    db: Session,
    embedding_provider: EmbeddingProvider,
    top_k: int = DEFAULT_TOP_K,
) -> list[ScoredChunk]:
    """
    Returns this document's `top_k` chunks most semantically similar to
    `query`, most similar first.

    This is a brute-force scan — load every chunk for the document,
    score each one, sort — not an indexed lookup. See the note on
    DocumentChunk in db/models.py for why that's the right tradeoff at
    LearnFlow's current scale, and _cosine_similarity above for why
    scoring itself doesn't need a numerical library either.

    Returns an empty list if the document has no chunks yet (it hasn't
    been indexed) rather than raising — "no results" and "not indexed"
    are both legitimately "nothing to return" from retrieval's point of
    view; a caller that needs to tell those apart (see routes_rag.py)
    checks for indexing separately, before calling this.
    """
    chunks = (
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    )
    if not chunks:
        return []

    query_embedding = await embedding_provider.embed_query(query)

    scored_chunks = [
        ScoredChunk(chunk=chunk, score=_cosine_similarity(query_embedding, chunk.embedding))
        for chunk in chunks
    ]
    scored_chunks.sort(key=lambda scored: scored.score, reverse=True)

    return scored_chunks[:top_k]
