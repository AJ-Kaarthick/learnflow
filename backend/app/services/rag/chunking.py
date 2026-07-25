"""
Splits a document's extracted text into overlapping chunks, ready to be
embedded and stored by embedding_service.py.

Why chunk at all: an embedding model compresses a piece of text into
ONE vector representing its overall meaning. Embed an entire 20-page
PDF as a single vector and that vector is a blurry average of
everything in it — a query about page 14 ends up looking no more
similar to it than a query about page 2. Chunking breaks the document
into pieces small enough that each vector represents one reasonably
specific idea, so semantic search can point at the actual paragraph
that answers a question instead of just "the document, generally."

Why overlap: without it, a sentence that happens to fall across a
chunk boundary gets sliced in half, and neither half fully represents
its own meaning on its own. A small overlap — each chunk repeats the
tail end of the previous one — makes it far less likely that the one
boundary that matters for a given query lands exactly on a sentence
break.

Character-based, not token-based, on purpose: LearnFlow's other AI
features (see MAX_CHARACTERS_FOR_PROMPT in summary_service.py and
friends) already measure text in characters rather than tokens, and
introducing a tokenizer here just for chunking would mean this file
measures text differently than the rest of the codebase for no real
benefit — chunk boundaries don't need to be token-exact, just
"roughly this much text, split on a word boundary."
"""

# ~1000 characters is short enough that a chunk is about one idea (a
# paragraph or two of a typical PDF), not an entire section — and long
# enough to still carry real context on its own, since a query has to
# match the whole chunk's meaning, not just one word in it.
CHUNK_SIZE_CHARACTERS = 1000

# About 15% of the chunk size. Enough to carry a sentence or two of
# shared context across a boundary; much more than this would mean
# storing (and later embedding) the same text repeatedly for little
# added benefit.
CHUNK_OVERLAP_CHARACTERS = 150


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_CHARACTERS,
    overlap: int = CHUNK_OVERLAP_CHARACTERS,
) -> list[str]:
    """
    Splits `text` into a list of chunks of roughly `chunk_size`
    characters each, with `overlap` characters of repeated text between
    consecutive chunks. Chunk boundaries snap to the nearest preceding
    space so words are never cut in half.

    Returns an empty list for empty/whitespace-only text (nothing to
    chunk), and a single chunk if `text` is already shorter than
    `chunk_size` (nothing to split).
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    # Collapses all runs of whitespace (spaces, tabs, the blank lines
    # pdf_service.py inserts between pages) into single spaces. This
    # keeps the word-boundary search below simple — it only ever has
    # to look for " " — and chunk meaning doesn't depend on preserving
    # the original line breaks.
    normalized = " ".join(text.split())
    if not normalized:
        return []

    text_length = len(normalized)
    if text_length <= chunk_size:
        return [normalized]

    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0

    while start < text_length:
        end = min(start + chunk_size, text_length)

        # Not the last chunk -> don't cut a word in half. Back up to
        # the nearest preceding space so this chunk ends between
        # words. If there's no space to back up to (one very long
        # unbroken "word"), fall back to the hard cut.
        if end < text_length:
            boundary = normalized.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        # Advance by the fixed step, not to `end` — this is what
        # creates the overlap, and (since step > 0 is guaranteed by
        # the overlap < chunk_size check above) what guarantees this
        # loop always makes progress.
        start += step

        # A fixed character step can land in the middle of a word.
        # Nudge forward to the start of the next word so the *next*
        # chunk doesn't begin with a word fragment — the counterpart
        # of snapping `end` backward to a space above.
        if start < text_length and normalized[start - 1] != " ":
            next_space = normalized.find(" ", start)
            start = next_space + 1 if next_space != -1 else text_length

    return chunks
