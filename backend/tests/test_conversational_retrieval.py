"""
Milestone 6: conversational (history-aware) retrieval.

Covers two layers:

1. query_condensation.condense_query() in isolation — the new,
   single-responsibility piece that turns "question + history" into a
   standalone retrieval query. Fast, no HTTP, no embedding math.

2. The end-to-end effect through chat_service.answer_question() / the
   chat routes — proving that a follow-up question ("Explain it.")
   now actually retrieves the chunk it should, that this doesn't
   change what the model is asked or weaken hallucination prevention,
   and that ordinary (non-follow-up) chat is completely unaffected.

Layer 2 needs an embedding provider whose vectors actually depend on
query content (unlike test_chat.py's constant-vector FakeEmbeddingProvider,
which can't distinguish a good retrieval query from a bad one) and an
AI provider that can tell a condensation call apart from a generation
call (unlike test_chat.py's FakeAIProvider, which always returns the
same fixed string regardless of which stage is asking). Both are
defined locally below rather than imported, since no existing fake
supports scripting two different call sites independently.
"""

import asyncio
import io

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.db.database import SessionLocal
from app.db.models import Document
from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import NO_CONTEXT_ANSWER, answer_question
from app.services.rag.query_condensation import condense_query

# Two command sections concatenated, the same technique test_rag.py's
# CAT_AND_DOG_TEXT uses: long enough (well past CHUNK_SIZE_CHARACTERS)
# that chunking produces at least one ls-dominant chunk and one
# pwd-dominant chunk, so retrieval ranking is actually assertable.
LS_TEXT = "The ls command lists the files in a directory. " * 40
PWD_TEXT = "The pwd command prints the current working directory. " * 40
LS_AND_PWD_TEXT = LS_TEXT + PWD_TEXT

# A second document, entirely unrelated to ls/pwd, for the
# multi-document follow-up test.
GREP_TEXT = "The grep command searches text using patterns. " * 60


class KeywordEmbeddingProvider(EmbeddingProvider):
    """
    Returns a 2D vector based on whether a text is ls-dominant,
    pwd-dominant, or grep-dominant — same technique as test_rag.py's
    and test_multi_document_chat.py's keyword-based fakes. This is
    what makes it possible to prove retrieval actually used the
    *condensed* query rather than the raw follow-up text: "Explain
    it." and "Explain how the ls command works" embed to different
    vectors here, exactly like a real embedding model would.
    """

    async def embed_document(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        lowered = text.lower()
        ls_score = lowered.count("ls") + lowered.count("list")
        pwd_score = lowered.count("pwd") + lowered.count("working directory")
        grep_score = lowered.count("grep")
        if ls_score >= pwd_score and ls_score >= grep_score and ls_score > 0:
            return [1.0, 0.0, 0.0]
        if pwd_score >= ls_score and pwd_score >= grep_score and pwd_score > 0:
            return [0.0, 1.0, 0.0]
        if grep_score > 0:
            return [0.0, 0.0, 1.0]
        return [0.0, 0.0, 0.0]


class ScriptedAIProvider(AIProvider):
    """
    Distinguishes a condensation call (query_condensation.py's prompt,
    identifiable by its "Standalone query:" marker, present only in
    _build_condense_prompt's output) from a generation call
    (chat_service.build_chat_prompt's prompt, which has no such
    marker) — so a test can script "the model resolves the follow-up
    to X" independently of "the model's final answer is Y". Records
    every prompt, in order, so tests can also assert on exactly what
    the generation step was asked.
    """

    def __init__(
        self,
        condensed_query: str | None = None,
        answer: str = "The answer, grounded in the retrieved excerpts.",
        raise_on_condense: bool = False,
    ) -> None:
        self.prompts: list[str] = []
        self._condensed_query = condensed_query
        self._answer = answer
        self._raise_on_condense = raise_on_condense

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        is_condense_call = "Standalone query:" in prompt
        if is_condense_call:
            if self._raise_on_condense:
                raise AIProviderError("Simulated condensation failure.")
            if self._condensed_query is not None:
                return self._condensed_query
        return self._answer

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    @property
    def last_prompt(self) -> str | None:
        return self.prompts[-1] if self.prompts else None


class AlwaysCalledAIProvider(AIProvider):
    """Fails the test loudly if it's ever called — for asserting a code path is skipped entirely."""

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError(f"AI provider should not have been called, got prompt: {prompt!r}")


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload_and_index_document(client: TestClient, filename: str, text: str) -> str:
    pdf_bytes = _make_test_pdf(text)
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]
    client.post(f"/api/v1/documents/{document_id}/index")
    return document_id


# ---------------------------------------------------------------------------
# Layer 1: condense_query() in isolation
# ---------------------------------------------------------------------------


def test_condense_query_skips_ai_call_when_no_history():
    """
    No history means there's nothing to resolve — the raw-question
    behavior from before this milestone, at zero added cost. Uses
    AlwaysCalledAIProvider so the test fails loudly if this ever
    regresses into calling out for a no-op rewrite.
    """
    result = asyncio.run(
        condense_query("What is ls?", history=[], ai_provider=AlwaysCalledAIProvider())
    )
    assert result == "What is ls?"


def test_condense_query_resolves_reference_using_history():
    provider = ScriptedAIProvider(condensed_query="Explain how the ls command works.")
    result = asyncio.run(
        condense_query(
            "Explain it.",
            history=[
                {"role": "user", "content": "What is ls?"},
                {"role": "assistant", "content": "ls lists files in a directory."},
            ],
            ai_provider=provider,
        )
    )
    assert result == "Explain how the ls command works."
    assert provider.call_count == 1
    # The prompt sent for condensation must include both the history
    # and the follow-up, and must not ask the model to answer.
    assert "What is ls?" in provider.last_prompt
    assert "Explain it." in provider.last_prompt
    assert "Do not answer the question" in provider.last_prompt


def test_condense_query_falls_back_to_original_on_provider_error():
    """
    A condensation failure must degrade to Milestone 5 behavior (raw
    question), never raise and never break the chat request.
    """
    provider = ScriptedAIProvider(raise_on_condense=True)
    result = asyncio.run(
        condense_query(
            "Explain it.",
            history=[{"role": "user", "content": "What is ls?"}],
            ai_provider=provider,
        )
    )
    assert result == "Explain it."


def test_condense_query_falls_back_to_original_when_rewrite_is_blank():
    provider = ScriptedAIProvider(condensed_query="   ")
    result = asyncio.run(
        condense_query(
            "Explain it.",
            history=[{"role": "user", "content": "What is ls?"}],
            ai_provider=provider,
        )
    )
    assert result == "Explain it."


# ---------------------------------------------------------------------------
# Layer 2: end-to-end through the chat routes
# ---------------------------------------------------------------------------


def test_pronoun_follow_up_retrieves_correct_chunk():
    """
    The exact failure from the Milestone 5 bug report: "What is ls?"
    followed by "Explain it." Without condensation, "Explain it."
    embeds to [0, 0, 0] (KeywordEmbeddingProvider) and would rank the
    pwd chunk no differently from the ls chunk. With condensation
    resolving "it" to ls, retrieval must favor the ls chunk.
    """
    scripted_provider = ScriptedAIProvider(
        condensed_query="Explain how the ls command works.",
        answer="ls lists the files in a directory.",
    )
    app.dependency_overrides[get_ai_provider] = lambda: scripted_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, "commands.pdf", LS_AND_PWD_TEXT)

    response = client.post(
        f"/api/v1/documents/{document_id}/chat",
        json={
            "question": "Explain it.",
            "top_k": 2,
            "history": [
                {"role": "user", "content": "What is ls?"},
                {"role": "assistant", "content": "ls lists files in a directory."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert body["answer"] == "ls lists the files in a directory."
    # The retrieved sources must be dominated by ls content, not pwd —
    # this is the actual regression check for the bug report.
    assert body["sources"], "expected at least one retrieved chunk"
    assert all("ls" in source["content"].lower() for source in body["sources"])
    assert not any("pwd" in source["content"].lower() for source in body["sources"])

    # The model is still asked the literal question the user typed,
    # not the condensed one — condensation is retrieval-only.
    generation_prompt = scripted_provider.prompts[-1]
    assert "Question: Explain it." in generation_prompt

    app.dependency_overrides.clear()


def test_context_dependent_follow_up_tell_me_more():
    """Same shape as the pronoun test, but with an elliptical ("Tell me more.") rather than a pronoun follow-up, and about pwd instead of ls."""
    scripted_provider = ScriptedAIProvider(
        condensed_query="Tell me more about the pwd command.",
        answer="pwd prints the current working directory path.",
    )
    app.dependency_overrides[get_ai_provider] = lambda: scripted_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, "commands.pdf", LS_AND_PWD_TEXT)

    response = client.post(
        f"/api/v1/documents/{document_id}/chat",
        json={
            "question": "Tell me more.",
            "top_k": 2,
            "history": [
                {"role": "user", "content": "What is pwd?"},
                {"role": "assistant", "content": "pwd prints the working directory."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert body["sources"]
    assert all("pwd" in source["content"].lower() for source in body["sources"])

    app.dependency_overrides.clear()


def test_multi_document_follow_up_conversation():
    """
    "Summarize the first document." then "Compare it with the second
    document." across two selected documents. The condensed query
    should reference both topics so per-document top_k (unchanged in
    retrieval_service.py) still surfaces chunks from both documents —
    proving multi-document follow-ups keep every selected document
    represented, the same guarantee Milestone 5 already made for
    single-turn multi-document questions.
    """
    scripted_provider = ScriptedAIProvider(
        condensed_query="Compare ls and grep commands.",
        answer="ls lists files; grep searches text — different purposes.",
    )
    app.dependency_overrides[get_ai_provider] = lambda: scripted_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    ls_id = _upload_and_index_document(client, "ls.pdf", LS_TEXT)
    grep_id = _upload_and_index_document(client, "grep.pdf", GREP_TEXT)

    response = client.post(
        "/api/v1/documents/chat",
        json={
            "document_ids": [ls_id, grep_id],
            "question": "Compare it with the second document.",
            "history": [
                {"role": "user", "content": "Summarize the first document."},
                {"role": "assistant", "content": "It explains the ls command."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    represented_documents = {source["document_id"] for source in body["sources"]}
    assert represented_documents == {ls_id, grep_id}

    app.dependency_overrides.clear()


def test_semantically_equivalent_follow_ups_retrieve_the_same_target():
    """
    Retrieval robustness for semantically equivalent queries: two
    differently-worded follow-ups with the same underlying intent
    ("Explain it." vs "Can you go into more detail on that?") must
    both resolve — via condensation — to a query that retrieves the
    ls chunk, not just one phrasing of it. This is the "compare" vs
    "tell the differences" wording-sensitivity gap from the Milestone
    5 report, addressed for the conversational case condensation
    covers directly.
    """
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, "commands.pdf", LS_AND_PWD_TEXT)

    history = [
        {"role": "user", "content": "What is ls?"},
        {"role": "assistant", "content": "ls lists files in a directory."},
    ]

    for follow_up in ("Explain it.", "Can you go into more detail on that?"):
        scripted_provider = ScriptedAIProvider(
            condensed_query="Explain the ls command in more detail.",
            answer="ls lists the files in a directory.",
        )
        app.dependency_overrides[get_ai_provider] = lambda p=scripted_provider: p

        response = client.post(
            f"/api/v1/documents/{document_id}/chat",
            json={"question": follow_up, "top_k": 2, "history": history},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["sources"], f"expected sources for follow-up: {follow_up!r}"
        assert all("ls" in source["content"].lower() for source in body["sources"])

    app.dependency_overrides.clear()


def test_hallucination_prevention_regression_with_condensation():
    """
    Condensation must never let history become factual evidence.
    Scripts a condensed query that legitimately retrieves ls content,
    but the model still decides (as it's free to) that the excerpts
    don't answer the question — the fixed NO_CONTEXT_ANSWER must still
    come through unchanged, and grounded must still be True (a correct
    "not answerable" is still a grounded response, same contract as
    Milestone 4/5).
    """
    scripted_provider = ScriptedAIProvider(
        condensed_query="Explain how the ls command works.",
        answer=NO_CONTEXT_ANSWER,
    )
    app.dependency_overrides[get_ai_provider] = lambda: scripted_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, "commands.pdf", LS_AND_PWD_TEXT)

    response = client.post(
        f"/api/v1/documents/{document_id}/chat",
        json={
            "question": "Explain it.",
            "history": [
                {"role": "user", "content": "What is ls?"},
                {"role": "assistant", "content": "ls lists files in a directory."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NO_CONTEXT_ANSWER
    assert body["grounded"] is True

    # The generation prompt still frames history as non-factual, and
    # still contains the grounding instructions unchanged.
    generation_prompt = scripted_provider.prompts[-1]
    assert "NOT a source of facts" in generation_prompt
    assert "ONLY the document" in generation_prompt
    assert "Question: Explain it." in generation_prompt

    app.dependency_overrides.clear()


def test_existing_single_turn_chat_is_unaffected():
    """
    Regression: a question with no history — the common case, and
    everything Milestone 5's manual testing checklist already verified
    as working (single-document factual questions, summarize the first
    document, etc.) — must not trigger condensation at all. Asserts
    exactly one AI call is made (generation only), so this milestone
    adds zero latency/cost to the case that already worked.
    """
    scripted_provider = ScriptedAIProvider(answer="ls lists the files in a directory.")
    app.dependency_overrides[get_ai_provider] = lambda: scripted_provider
    app.dependency_overrides[get_embedding_provider] = lambda: KeywordEmbeddingProvider()
    client = TestClient(app)
    document_id = _upload_and_index_document(client, "commands.pdf", LS_AND_PWD_TEXT)

    response = client.post(
        f"/api/v1/documents/{document_id}/chat",
        json={"question": "What is ls?"},
    )

    assert response.status_code == 200
    assert response.json()["grounded"] is True
    assert scripted_provider.call_count == 1

    app.dependency_overrides.clear()


def test_answer_question_service_level_uses_condensed_query_for_retrieval():
    """
    Direct service-level check (bypassing HTTP) that answer_question
    passes the condensed query — not the raw follow-up — to retrieval,
    while build_chat_prompt still gets the original question. Belt-
    and-suspenders alongside the route-level tests above, at the same
    level test_chat.py's existing direct answer_question() tests
    already operate at.
    """
    db = SessionLocal()
    try:
        document = Document(
            original_filename="commands.pdf",
            stored_filename="commands.pdf",
            status="ready",
            extracted_text=LS_AND_PWD_TEXT,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        from app.services.rag.embedding_service import index_document

        asyncio.run(index_document(document, db, KeywordEmbeddingProvider()))

        scripted_provider = ScriptedAIProvider(
            condensed_query="Explain how the ls command works.",
            answer="ls lists the files in a directory.",
        )

        result = asyncio.run(
            answer_question(
                documents=[document],
                question="Explain it.",
                db=db,
                ai_provider=scripted_provider,
                embedding_provider=KeywordEmbeddingProvider(),
                top_k=2,
                history=[
                    {"role": "user", "content": "What is ls?"},
                    {"role": "assistant", "content": "ls lists files in a directory."},
                ],
            )
        )

        assert result.grounded is True
        assert result.chunks, "expected at least one retrieved chunk"
        assert all("ls" in scored.chunk.content.lower() for scored in result.chunks)
        assert scripted_provider.call_count == 2  # condense, then generate
    finally:
        db.close()
