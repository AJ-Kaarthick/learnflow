"""
The "read path" of the RAG foundation: given one or more documents and
a natural-language query, returns the chunks most semantically similar
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

Milestone 3 — intelligent multi-document retrieval: this module always
retrieved independently *per document* rather than pooling globally
(see the balanced-retrieval note on retrieve_relevant_chunks below),
which was already the right foundation for multi-document chat. This
milestone builds three things on top of that foundation, all still
inside this one file because they're all still "what does retrieval
return," not "what does a caller do with it":

1. An adaptive per-document budget (compute_adaptive_top_k) instead of
   a single fixed DEFAULT_TOP_K for every request, regardless of how
   many documents are selected.
2. A relevance signal per document (DocumentRetrievalSummary) — not
   just "did this document contribute chunks" (it always does, as
   long as it's indexed) but "did any of those chunks actually look
   relevant to the query." Callers that need to explain *why* an
   answer is thin (chat_service.py) read this instead of re-deriving
   it from raw scores themselves.
3. Duplicate/near-duplicate removal across the merged, globally-ranked
   result — repeated boilerplate (title pages, disclaimers, repeated
   section headings) showing up once per document it appears in was
   already possible before this milestone, and gets worse as more
   documents are selected at once.
"""

import math
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.db.models import DocumentChunk
from app.services.ai.embedding_provider import EmbeddingProvider

# Retained as the "top_k per document" figure the rest of the codebase
# has always known about (schemas/rag.py's SearchRequest still uses
# this as a plain, fixed default — single-document search isn't part
# of this milestone's adaptive-budget scope, see routes_rag.py). Chat
# retrieval no longer uses this directly; see compute_adaptive_top_k.
DEFAULT_TOP_K = 5

# --------------------------------------------------------------------
# Adaptive retrieval budget (Milestone 3, requirement 2)
# --------------------------------------------------------------------
#
# "top_k" for chat retrieval is no longer one fixed number — it scales
# with how many documents are selected, on the theory that a question
# about a single document deserves deep coverage of that document,
# while a question spanning many documents needs less *per document*
# (each one only has to contribute its most relevant handful of
# chunks) but must still guarantee every selected document shows up
# with enough evidence to actually be compared, not just represented
# by a token chunk.
#
# The table below is deliberately front-loaded (a much larger budget
# for 1-2 documents) rather than a smooth linear taper — the jump from
# "a whole document's worth of attention" to "sharing context with
# other documents" is the meaningful transition, not the exact curve
# after that. MIN_ADAPTIVE_TOP_K is the floor for 4+ documents: keep
# retrieving more evidence when there's room for it (per this
# milestone's "prioritize answer quality" requirement), but never so
# little per document that a document's own best chunk can't make it
# into the merged result.
_ADAPTIVE_TOP_K_BY_DOCUMENT_COUNT = {1: 8, 2: 6, 3: 5}
MIN_ADAPTIVE_TOP_K = 4


def compute_adaptive_top_k(document_count: int) -> int:
    """
    Returns how many chunks to retrieve *per document* for a request
    spanning `document_count` selected documents.

    Worked example of why this stays safely below Gemini's context
    window without needing a hard cap here: the most documents a
    single request can select is MAX_DOCUMENT_IDS (see
    schemas/chat.py), currently 10. Even at 10 documents, this
    function's floor of MIN_ADAPTIVE_TOP_K chunks each is 40 chunks
    total; at CHUNK_SIZE_CHARACTERS (see chunking.py, ~1000 characters
    per chunk) that's roughly 40,000 characters of context — a small
    fraction of what Gemini's context window actually holds. Nothing
    here needs its own separate context-length cap on top of that;
    the per-document floor is already conservative at the maximum
    document count the API accepts.
    """
    if document_count <= 0:
        return 0
    return _ADAPTIVE_TOP_K_BY_DOCUMENT_COUNT.get(document_count, MIN_ADAPTIVE_TOP_K)


# --------------------------------------------------------------------
# Relevance and duplicate thresholds
# --------------------------------------------------------------------

# A cosine similarity a document's single best-matching chunk has to
# clear to count as "this document actually has something relevant to
# say about the query" (DocumentRetrievalSummary.has_relevant_evidence
# below), as opposed to "this document was included because balanced
# retrieval guarantees every selected document a chance, and this was
# the least-irrelevant chunk it had." 0.5 sits comfortably above what
# two genuinely unrelated passages score against most text embedding
# models (typically well under that) while still being well below
# what a passage that actually addresses the query scores — a
# deliberately conservative middle, not a tuned-to-the-decimal
# threshold. Chat-level callers (chat_service.py) use this signal for
# more informative failure messages; it never removes a chunk from
# the retrieved set — that's still balanced retrieval's job.
RELEVANCE_SCORE_THRESHOLD = 0.5

# How similar (via difflib's SequenceMatcher ratio, 0.0-1.0) two
# chunks' normalized text have to be before the weaker-scoring one is
# treated as a duplicate of the stronger one and dropped from the
# merged result. High on purpose: chunking's overlap (see
# CHUNK_OVERLAP_CHARACTERS in chunking.py) already makes *adjacent*
# chunks from the same document share some text by design, and that's
# not the "repeated boilerplate" this exists to catch — it's expected
# structure. What this threshold targets is closer to "the same
# passage effectively verbatim" (a repeated cover page, disclaimer, or
# section heading appearing in more than one place retrieval looked),
# which scores far higher than ordinary chunk overlap ever does.
DUPLICATE_SIMILARITY_THRESHOLD = 0.85


@dataclass
class ScoredChunk:
    """A DocumentChunk paired with how similar it is to a query (1.0 = most similar)."""

    chunk: DocumentChunk
    score: float


@dataclass
class DocumentRetrievalSummary:
    """
    Per-document outcome of one retrieval call — one of these exists
    for every document_id passed to retrieve_relevant_chunks, in the
    same order, regardless of whether that document ended up
    contributing any chunks to the final (deduplicated) result.

    This is what lets a caller answer "which of the documents the user
    selected actually had something relevant to say," a question the
    merged ScoredChunk list alone can't answer once deduplication has
    possibly removed a document's only chunk in favor of a
    stronger-scoring duplicate elsewhere.
    """

    document_id: str
    # How many chunks this document contributed *before* deduplication
    # (i.e. up to the adaptive/explicit top_k for this document). Zero
    # only means "not indexed" — indexed documents always contribute
    # at least one chunk, however weak, per balanced retrieval.
    retrieved_chunk_count: int
    # This document's single best-scoring chunk's score, or 0.0 if it
    # contributed no chunks at all.
    best_score: float
    # best_score >= RELEVANCE_SCORE_THRESHOLD — see that constant.
    has_relevant_evidence: bool


@dataclass
class RetrievalResult:
    """
    Everything one retrieve_relevant_chunks call produces: the merged,
    ranked, deduplicated chunks a caller actually grounds an answer
    in, plus the per-document summary that explains how each selected
    document fared, whether or not it ended up represented in `chunks`.
    """

    chunks: list[ScoredChunk]
    document_summaries: list[DocumentRetrievalSummary] = field(default_factory=list)


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


def _normalize_for_dedup(text: str) -> str:
    """Case- and whitespace-insensitive form used only to compare chunks for near-duplication."""
    return " ".join(text.lower().split())


def _is_near_duplicate(normalized_a: str, normalized_b: str) -> bool:
    return SequenceMatcher(None, normalized_a, normalized_b).ratio() >= DUPLICATE_SIMILARITY_THRESHOLD


def _merge_rank_and_deduplicate(
    per_document_chunks: dict[str, list[ScoredChunk]],
) -> list[ScoredChunk]:
    """
    Merges every document's independently-retrieved chunks into one
    list, ranks it globally by score, and removes duplicate/near-
    duplicate passages — keeping the strongest-scoring copy of any
    passage that shows up more than once (e.g. the same boilerplate
    disclaimer or section heading indexed from more than one source).

    Balanced representation survives deduplication on purpose: each
    document's single best-scoring chunk is exempt from removal, even
    if it happens to closely resemble a higher-scoring chunk from
    another document. Without that exemption, deduplication could
    silently undo the entire point of per-document retrieval — a
    document whose content is mostly boilerplate could lose its one
    genuinely relevant chunk just for resembling another document's
    boilerplate too closely, leaving it unrepresented in the final
    context exactly like the "one document dominates" failure mode
    balanced retrieval exists to prevent.
    """
    all_chunks = [chunk for chunks in per_document_chunks.values() for chunk in chunks]
    all_chunks.sort(key=lambda scored: scored.score, reverse=True)

    protected_chunk_ids = {
        chunks[0].chunk.id for chunks in per_document_chunks.values() if chunks
    }

    kept: list[ScoredChunk] = []
    kept_normalized: list[str] = []
    for scored in all_chunks:
        normalized = _normalize_for_dedup(scored.chunk.content)
        is_duplicate = any(_is_near_duplicate(normalized, existing) for existing in kept_normalized)
        if is_duplicate and scored.chunk.id not in protected_chunk_ids:
            continue
        kept.append(scored)
        kept_normalized.append(normalized)

    return kept


async def retrieve_relevant_chunks(
    document_ids: list[str],
    query: str,
    db: Session,
    embedding_provider: EmbeddingProvider,
    top_k: int | None = None,
) -> RetrievalResult:
    """
    Returns the chunks most semantically similar to `query` — merged,
    globally ranked (most similar first), and deduplicated — scored
    independently *within each* document in `document_ids` before
    merging, rather than pooling every document's chunks together and
    taking one global top_k.

    That distinction only matters once `document_ids` has more than
    one entry, but it matters a lot then: for a multi-document question
    like "compare deadlocks in Operating Systems and DBMS", one global
    top_k could easily return five chunks that are all from whichever
    single document happens to score highest overall, leaving the
    other selected document completely unrepresented in the answer's
    context — the opposite of what multi-document chat is for.
    Guaranteeing each selected document gets up to `top_k` chunks means
    a comparison question always has something from every document
    selected to compare, at the cost of a somewhat larger combined
    context than one global top_k would produce — worth it at
    LearnFlow's scale.

    `top_k` means "up to top_k chunks per document," same as before
    this milestone. Passing `None` (the default) uses
    compute_adaptive_top_k(len(document_ids)) instead of one fixed
    number — the right choice for chat, where nothing about the
    request tells retrieval how much context to fetch. A caller that
    knows exactly how many chunks it wants (e.g. a client-specified
    top_k on a chat request, or routes_rag.py's single-document search
    endpoint) can still pass an explicit value, which is always
    honored as-is.

    Single-document retrieval (search, single-document chat) is just
    the len(document_ids) == 1 case of this same function — there's
    one code path for both, not a separate implementation.

    Still a brute-force scan per document, not an indexed lookup — see
    the note on DocumentChunk in db/models.py — and the embedding
    query itself only runs once and is reused across every document,
    so retrieving across several documents costs the same one
    embedding call as retrieving from one.

    Returns an empty chunk list (with a DocumentRetrievalSummary per
    document, all showing zero chunks) if none of `document_ids` have
    any indexed chunks yet, rather than raising — same reasoning as
    the original single-document version had: "no results" and "not
    indexed" are both legitimately "nothing to return" from
    retrieval's point of view; a caller that needs to tell those apart
    (see routes_rag.py, routes_chat.py) checks for indexing separately,
    before calling this.
    """
    if not document_ids:
        return RetrievalResult(chunks=[], document_summaries=[])

    effective_top_k = top_k if top_k is not None else compute_adaptive_top_k(len(document_ids))

    query_embedding = await embedding_provider.embed_query(query)

    per_document_chunks: dict[str, list[ScoredChunk]] = {}
    document_summaries: list[DocumentRetrievalSummary] = []

    for document_id in document_ids:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
        if not chunks:
            document_summaries.append(
                DocumentRetrievalSummary(
                    document_id=document_id,
                    retrieved_chunk_count=0,
                    best_score=0.0,
                    has_relevant_evidence=False,
                )
            )
            continue

        scored_for_document = [
            ScoredChunk(chunk=chunk, score=_cosine_similarity(query_embedding, chunk.embedding))
            for chunk in chunks
        ]
        scored_for_document.sort(key=lambda scored: scored.score, reverse=True)
        top_for_document = scored_for_document[:effective_top_k]

        per_document_chunks[document_id] = top_for_document
        best_score = top_for_document[0].score
        document_summaries.append(
            DocumentRetrievalSummary(
                document_id=document_id,
                retrieved_chunk_count=len(top_for_document),
                best_score=best_score,
                has_relevant_evidence=best_score >= RELEVANCE_SCORE_THRESHOLD,
            )
        )

    merged_chunks = _merge_rank_and_deduplicate(per_document_chunks)
    return RetrievalResult(chunks=merged_chunks, document_summaries=document_summaries)
