from app.services.rag.chunking import chunk_text


def test_chunk_text_returns_empty_list_for_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_returns_single_chunk_when_shorter_than_chunk_size():
    assert chunk_text("A short document.", chunk_size=1000) == ["A short document."]


def test_chunk_text_splits_long_text_into_multiple_chunks():
    text = "word " * 500  # 2500 characters
    chunks = chunk_text(text, chunk_size=1000, overlap=150)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000


def test_chunk_text_does_not_cut_words_in_half():
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet " * 20
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    words = set(text.split())
    for chunk in chunks:
        for token in chunk.split():
            assert token in words


def test_chunk_text_consecutive_chunks_overlap():
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=1000, overlap=150)

    # The tail of one chunk should reappear at the head of the next —
    # that's what "overlap" means. Comparing a trailing/leading slice
    # (rather than the whole chunk) keeps this robust to the exact
    # word-boundary snapping chunk_text does.
    first_tail = chunks[0][-100:]
    second_head = chunks[1][:200]
    assert first_tail[-20:] in second_head


def test_chunk_text_collapses_whitespace():
    text = "Page one.\n\n\nPage two.   Page three."
    chunks = chunk_text(text, chunk_size=1000)

    assert chunks == ["Page one. Page two. Page three."]


def test_chunk_text_rejects_overlap_not_smaller_than_chunk_size():
    try:
        chunk_text("some text", chunk_size=100, overlap=100)
        assert False, "expected a ValueError"
    except ValueError:
        pass


def test_chunk_text_every_chunk_appears_in_source_order():
    text = "sentence number " + " ".join(str(n) for n in range(400))
    chunks = chunk_text(text, chunk_size=200, overlap=40)

    normalized = " ".join(text.split())
    search_start = 0
    for chunk in chunks:
        position = normalized.find(chunk, search_start - 40 if search_start > 40 else 0)
        assert position != -1
        search_start = position
