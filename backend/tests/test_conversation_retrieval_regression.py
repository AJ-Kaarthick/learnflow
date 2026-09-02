"""
Regression coverage for a manually-observed retrieval/grounding
problem: in a persisted, multi-document conversation
(POST /conversations/{id}/messages), a first broad question ("what are
these documents about?") was answered correctly, but a specific
follow-up question in the SAME conversation, about content that was
genuinely present in one of the selected documents, came back as
NO_CONTEXT_ANSWER ("I couldn't find the answer to this question in the
uploaded document") even though the UI still showed both documents
selected and the response still showed retrieved sources.

Investigation traced the full path this endpoint exercises --
ChatPage/ChatPanel request construction, ConversationDocument-backed
document-scope resolution, database-persisted history loading,
query_condensation.condense_query, retrieval_service.retrieve_relevant_chunks,
chat_service.build_chat_prompt, and generation -- and found no
deterministic defect: every one of the 350 pre-existing backend tests
already passed, and the RAG pipeline this endpoint calls
(chat_service.answer_question) is byte-for-byte the same one
test_conversational_retrieval.py already covers thoroughly.

What WAS a real gap: none of the existing multi-turn tests for this
specific endpoint (test_conversation_messages.py) use a
content-sensitive embedding provider -- they use FakeEmbeddingProvider,
a constant vector, so a second-turn question retrieving the *correct*
document's content through the persisted-conversation path specifically
(as opposed to the older, non-persisted /documents/chat path
test_conversational_retrieval.py exercises) was never actually proven,
only that retrieval returned *something*. This file closes that gap.

Every test below uses two documents, orthogonal keyword-sensitive
embeddings (same technique as test_multi_document_chat.py's
cats-vs-dogs KeywordEmbeddingProvider), and realistic DBMS-course-style
content -- one document about SQL single-row functions, the other
about DDL/DML statements -- deliberately mirroring the two documents
and the "difference between DDL and DML"-style follow-up questions
from the manual report as closely as a scripted test can. A
well-behaved AI provider is used for query condensation (one that
follows query_condensation.py's own documented contract -- "if the
follow-up question is already standalone ... return it unchanged" --
by literally extracting and echoing the follow-up text, rather than a
fixed/unrelated string) precisely so these tests isolate ONE question:
when condensation behaves exactly as designed, does the rest of this
endpoint's wiring (history persistence, document-scope resolution,
retrieval, prompt construction) still get the right content to the
model, turn after turn? That's the only part a code fix could
possibly address; a live model failing to follow its own condensation
instructions is a model-behavior question, not a code defect, and is
out of scope for these tests (see the investigation report).

If every test in this file passes against the unmodified implementation,
that is direct evidence the class of failure observed in manual testing
is NOT caused by a deterministic bug in the conversation-persistence,
document-selection, or conversation-naming (V2.4 Milestone 2) code.
"""

import io
import re

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app
from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import NO_CONTEXT_ANSWER

# Deliberately styled after the two documents in the manual report
# ("EX-single row function.docx", "EX-DDL&DML.docx") -- one document
# entirely about SQL single-row functions, the other entirely about
# DDL/DML statements, repeated to exceed CHUNK_SIZE_CHARACTERS the same
# way test_multi_document_chat.py's CATS_TEXT/DOGS_TEXT do.
SINGLE_ROW_FUNCTION_TEXT = (
    "Single row functions such as UPPER, LOWER, ROUND, and SUBSTR operate "
    "on one row at a time and return exactly one result per row processed. "
) * 60
DDL_DML_TEXT = (
    "DDL statements such as CREATE TABLE, ALTER TABLE, and DROP TABLE "
    "define and modify the structure of a database. DML statements such "
    "as INSERT, UPDATE, and DELETE modify the data stored inside existing "
    "tables. "
) * 60

SINGLE_ROW_FUNCTION_FILENAME = "EX-single row function.pdf"
DDL_DML_FILENAME = "EX-DDL&DML.pdf"


class DBMSKeywordEmbeddingProvider(EmbeddingProvider):
    """
    Content-sensitive 2D embedding fake, same technique as
    test_multi_document_chat.py's cats-vs-dogs KeywordEmbeddingProvider
    (chosen over test_conversation_messages.py's FakeEmbeddingProvider,
    a constant vector, precisely because a constant vector can't prove
    retrieval favors the document whose content actually matches the
    query -- see this file's module docstring). Axis 0 leans toward
    single-row-function vocabulary, axis 1 toward DDL/DML vocabulary --
    orthogonal by construction so a query that's purely about one topic
    scores the other document's chunks at exactly 0.0, the same
    "sharpest possible test" reasoning test_multi_document_chat.py uses.
    """

    _FUNCTION_TERMS = ("single row", "upper", "lower", "round", "substr")
    _DDL_DML_TERMS = (
        "ddl",
        "dml",
        "create table",
        "alter table",
        "drop table",
        "insert",
        "update",
        "delete",
    )

    async def embed_document(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)

    @classmethod
    def _vector_for(cls, text: str) -> list[float]:
        lowered = text.lower()
        function_count = sum(lowered.count(term) for term in cls._FUNCTION_TERMS)
        ddl_dml_count = sum(lowered.count(term) for term in cls._DDL_DML_TERMS)
        if function_count > ddl_dml_count:
            return [1.0, 0.0]
        if ddl_dml_count > function_count:
            return [0.0, 1.0]
        return [0.5, 0.5]


class AutoCondenseAIProvider(AIProvider):
    """
    Simulates a condensation call that follows query_condensation.py's
    own documented contract exactly: "If the follow-up question is
    already standalone and doesn't depend on the conversation, return
    it unchanged." Every follow-up question used in these tests IS
    already standalone (none of them contain a pronoun or implicit
    reference -- exactly like the three failing examples in the manual
    report: "what is the difference between ddl and dml", "what is ddl
    and dml about", "what is ddl and dml in the 2nd document"), so a
    compliant model should always return them verbatim. This fake
    enforces that by construction (extracting the literal follow-up
    text from query_condensation._build_condense_prompt's own
    "Follow-up question: ...\\n\\nStandalone query:" format, rather than
    returning some fixed/unrelated string), which is what isolates
    "does the CODE wire things together correctly" from "does a live
    model follow its own instructions" -- see this file's module
    docstring.

    Distinguishes a condensation call from a generation call the same
    way test_conversational_retrieval.py's ScriptedAIProvider does (by
    the "Standalone query:" marker, present only in
    query_condensation._build_condense_prompt's output), and a title
    call from a chat call the same way
    test_conversation_messages.py's FakeAIProvider does (by
    conversation_titling.py's distinctive "descriptive title" wording)
    -- both established conventions in this test suite, reused rather
    than reinvented here.

    `no_context_generation_turns` lets a test script a specific
    *generation* call (1-indexed, counting only chat-answer calls --
    never condense or title calls) to return NO_CONTEXT_ANSWER instead
    of the default grounded answer, used by
    test_retrieval_recovers_after_an_unhelpful_turn below to plant an
    unhelpful prior turn in history and verify it doesn't corrupt a
    later, correctly-answerable turn.
    """

    _FOLLOW_UP_RE = re.compile(r"Follow-up question: (.*)\n\nStandalone query:", re.DOTALL)

    def __init__(
        self,
        answer: str = "The answer, grounded in the retrieved excerpts.",
        no_context_generation_turns: frozenset[int] = frozenset(),
    ) -> None:
        self.prompts: list[str] = []
        self._answer = answer
        self._no_context_generation_turns = no_context_generation_turns
        self._generation_call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)

        if "Standalone query:" in prompt:
            match = self._FOLLOW_UP_RE.search(prompt)
            if match is None:
                raise AssertionError(f"Condense prompt didn't match expected shape: {prompt!r}")
            return match.group(1).strip()

        if "descriptive title" in prompt:
            return "DBMS Study Session"

        self._generation_call_count += 1
        if self._generation_call_count in self._no_context_generation_turns:
            return NO_CONTEXT_ANSWER
        return self._answer

    @property
    def chat_prompts(self) -> list[str]:
        """Every generation-call prompt (never condense, never title), in order."""
        return [
            prompt
            for prompt in self.prompts
            if "Standalone query:" not in prompt and "descriptive title" not in prompt
        ]


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
    assert upload_response.status_code == 201, upload_response.text
    document_id = upload_response.json()["id"]
    index_response = client.post(f"/api/v1/documents/{document_id}/index")
    assert index_response.status_code == 201, index_response.text
    return document_id


def _create_conversation(client: TestClient, document_ids: list[str]) -> str:
    response = client.post("/api/v1/conversations", json={"document_ids": document_ids})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _send_message(client: TestClient, conversation_id: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _two_document_conversation(client: TestClient) -> tuple[str, str, str]:
    """Returns (conversation_id, single_row_function_document_id, ddl_dml_document_id)."""
    function_doc_id = _upload_and_index_document(
        client, SINGLE_ROW_FUNCTION_FILENAME, SINGLE_ROW_FUNCTION_TEXT
    )
    ddl_dml_doc_id = _upload_and_index_document(client, DDL_DML_FILENAME, DDL_DML_TEXT)
    conversation_id = _create_conversation(client, [function_doc_id, ddl_dml_doc_id])
    return conversation_id, function_doc_id, ddl_dml_doc_id


# --------------------------------------------------------------------
# 1. The core reproduction: a broad first question, then the exact
#    class of specific follow-up question the manual report says
#    failed, in the same persisted conversation.
# --------------------------------------------------------------------


def test_second_turn_standalone_followup_retrieves_the_correct_document_content():
    """
    Mirrors the manual report as closely as a scripted test can: two
    DBMS documents selected, a broad "what are these documents about?"
    first question (which the report says worked), then a specific,
    already-standalone "difference between DDL and DML" follow-up in
    the SAME conversation (which the report says failed with
    NO_CONTEXT_ANSWER despite the UI still showing sources).

    Asserts far more than "sources were returned": that a source
    actually attributed to the DDL/DML document, containing real
    DDL/DML vocabulary, comes back; that the *generation* prompt (not
    just the sources list -- see this file's module docstring) contains
    an excerpt block explicitly labeled with the DDL/DML document's
    filename and DDL/DML content; and that the answer is grounded
    (True), not a NO_CONTEXT_ANSWER fallback.
    """
    ai_provider = AutoCondenseAIProvider(answer="DDL defines structure; DML modifies data.")
    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: DBMSKeywordEmbeddingProvider()
    client = TestClient(app)
    try:
        conversation_id, _function_doc_id, ddl_dml_doc_id = _two_document_conversation(client)

        first_turn = _send_message(
            client, conversation_id, "What are these documents about? Explain in detail."
        )
        assert first_turn["assistant_message"]["grounded"] is True

        second_turn = _send_message(
            client, conversation_id, "What is the difference between DDL and DML?"
        )
        assistant_message = second_turn["assistant_message"]

        # The failure mode from the manual report: a NO_CONTEXT_ANSWER
        # despite the question being answerable from the selected
        # documents. If this endpoint's wiring were dropping the
        # correct document's content on this second turn, this is
        # exactly the assertion that would catch it.
        assert assistant_message["grounded"] is True
        assert assistant_message["content"] != NO_CONTEXT_ANSWER

        sources = assistant_message["sources"]
        assert sources, "expected retrieved sources on a directly-answerable follow-up"
        ddl_dml_sources = [source for source in sources if source["document_id"] == ddl_dml_doc_id]
        assert ddl_dml_sources, (
            f"expected at least one source from {DDL_DML_FILENAME!r}, got sources from: "
            f"{sorted({source['document_name'] for source in sources})}"
        )
        assert any("ddl" in source["content"].lower() for source in ddl_dml_sources)
        assert any("dml" in source["content"].lower() for source in ddl_dml_sources)

        # The prompt actually sent to the model for this turn -- the
        # part sources alone can't prove (see module docstring).
        generation_prompt = ai_provider.chat_prompts[-1]
        assert f"— {DDL_DML_FILENAME}]" in generation_prompt
        assert "CREATE TABLE" in generation_prompt or "ddl" in generation_prompt.lower()
        assert "Question: What is the difference between DDL and DML?" in generation_prompt
    finally:
        app.dependency_overrides.clear()


def test_question_about_the_second_selected_document_does_not_lose_its_context():
    """
    The manual report's third failing example explicitly referenced
    "the 2nd document" ("what is ddl and dml in the 2nd document").
    Selects the two documents in the same order the report describes
    (single-row-function first, DDL/DML second) and asks a
    DDL/DML-specific follow-up, verifying the second-added document's
    content is still retrieved and still reaches the generation prompt
    -- i.e. that document-scope resolution across multiple messages
    doesn't silently favor or lose track of whichever document was
    added first vs. second.
    """
    ai_provider = AutoCondenseAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: DBMSKeywordEmbeddingProvider()
    client = TestClient(app)
    try:
        conversation_id, function_doc_id, ddl_dml_doc_id = _two_document_conversation(client)

        # Confirm the two documents actually persisted in selection
        # order before asking about "the 2nd" one.
        detail = client.get(f"/api/v1/conversations/{conversation_id}")
        assert detail.status_code == 200
        assert [doc["id"] for doc in detail.json()["documents"]] == [
            function_doc_id,
            ddl_dml_doc_id,
        ]

        _send_message(client, conversation_id, "What are these documents about?")
        second_turn = _send_message(client, conversation_id, "What is DDL and DML about?")

        assistant_message = second_turn["assistant_message"]
        assert assistant_message["grounded"] is True
        sources = assistant_message["sources"]
        assert any(source["document_id"] == ddl_dml_doc_id for source in sources)

        generation_prompt = ai_provider.chat_prompts[-1]
        assert f"— {DDL_DML_FILENAME}]" in generation_prompt
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------
# 2. Document IDs stay correctly associated with the conversation, and
#    every message's sources stay within that set, across several
#    sequential messages.
# --------------------------------------------------------------------


def test_document_association_and_message_sources_stay_correct_across_multiple_messages():
    """
    Directly verifies the brief's explicit ask: "verify that
    selected-document IDs remain correctly associated with the
    conversation/request after multiple messages." Sends three
    sequential messages in the same conversation and, after each,
    confirms (a) GET /conversations/{id} still reports exactly the two
    originally-selected documents, in the same order, and (b) every
    source any assistant message cites belongs to one of those two
    documents -- never a stray or wrong document id.
    """
    ai_provider = AutoCondenseAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: DBMSKeywordEmbeddingProvider()
    client = TestClient(app)
    try:
        conversation_id, function_doc_id, ddl_dml_doc_id = _two_document_conversation(client)
        expected_ids = {function_doc_id, ddl_dml_doc_id}

        questions = [
            "What are these documents about? Explain in detail.",
            "What is the difference between DDL and DML?",
            "What is DDL and DML about?",
        ]
        for question in questions:
            turn = _send_message(client, conversation_id, question)

            detail = client.get(f"/api/v1/conversations/{conversation_id}")
            assert detail.status_code == 200
            associated_ids = [doc["id"] for doc in detail.json()["documents"]]
            assert associated_ids == [function_doc_id, ddl_dml_doc_id], (
                f"document association changed after {question!r}: got {associated_ids}"
            )

            sources = turn["assistant_message"]["sources"] or []
            stray_sources = [s for s in sources if s["document_id"] not in expected_ids]
            assert not stray_sources, f"source(s) from an unselected document after {question!r}: {stray_sources}"
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------
# 3. An unhelpful prior turn (the exact "I couldn't find the answer"
#    text) accumulating in history doesn't corrupt a later,
#    correctly-answerable turn -- rules out a compounding-failure bug
#    at the code level.
# --------------------------------------------------------------------


def test_retrieval_recovers_after_an_unhelpful_prior_turn():
    """
    The manual report describes THREE consecutive failing follow-ups
    in the same conversation. By the third one, persisted history
    contains one or two prior "I couldn't find the answer..." turns.
    This scripts exactly that: turn 2's answer is forced to
    NO_CONTEXT_ANSWER (planting an unhelpful turn in history, the same
    text a real failure would have produced), then turn 3 asks again
    with different phrasing and must still correctly retrieve and
    ground an answer in the DDL/DML document -- proving accumulated
    "couldn't find" history doesn't shrink document scope or corrupt
    retrieval for a subsequent, answerable turn at the code level.
    """
    ai_provider = AutoCondenseAIProvider(no_context_generation_turns=frozenset({2}))
    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: DBMSKeywordEmbeddingProvider()
    client = TestClient(app)
    try:
        conversation_id, _function_doc_id, ddl_dml_doc_id = _two_document_conversation(client)

        _send_message(client, conversation_id, "What are these documents about?")

        second_turn = _send_message(
            client, conversation_id, "What is the difference between DDL and DML?"
        )
        second_answer = second_turn["assistant_message"]["content"]
        # chat_service.answer_question upgrades a bare NO_CONTEXT_ANSWER
        # to a more informative per-document message whenever more than
        # one document is selected and retrieval's own scoring
        # distinguishes relevant from irrelevant documents (Milestone 3,
        # V2.2 -- see _build_informative_no_match_answer). Both this
        # document's keyword-orthogonal embeddings score DDL/DML as
        # relevant and single-row-function as not, so that's exactly
        # what fires here -- existing, documented, correct behavior, not
        # a bug. This still plants an unhelpful turn in history (the raw
        # model answer this test scripted was NO_CONTEXT_ANSWER; the
        # user still got no real answer to their question either way),
        # it's just not the bare NO_CONTEXT_ANSWER string once upgraded.
        assert second_answer.startswith("I found relevant information in 1 of 2 selected documents")

        third_turn = _send_message(client, conversation_id, "What is DDL and DML about?")
        assistant_message = third_turn["assistant_message"]

        assert assistant_message["grounded"] is True
        assert assistant_message["content"] != NO_CONTEXT_ANSWER
        sources = assistant_message["sources"]
        assert any(source["document_id"] == ddl_dml_doc_id for source in sources)

        # The condensation call for turn 3 had turn 2's unhelpful answer
        # in its history -- confirm it was there (so this test is
        # actually exercising the scenario it claims to), and that the
        # query used for retrieval was still the literal turn-3
        # question, not something the discouraging prior answer dragged
        # off-topic.
        condense_prompts = [p for p in ai_provider.prompts if "Standalone query:" in p]
        assert len(condense_prompts) == 2  # one for turn 2, one for turn 3
        third_condense_prompt = condense_prompts[-1]
        assert second_answer in third_condense_prompt
        assert third_condense_prompt.strip().endswith(
            "Follow-up question: What is DDL and DML about?\n\nStandalone query:"
        )

        generation_prompt = ai_provider.chat_prompts[-1]
        assert f"— {DDL_DML_FILENAME}]" in generation_prompt
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------
# 4. Conversation-naming (Phase 4) doesn't interfere with the first
#    message's document scope or retrieved content.
# --------------------------------------------------------------------


def test_automatic_title_generation_does_not_affect_first_message_grounding():
    """
    V2.4 Milestone 2 Phase 4 added an automatic-title-generation call
    (conversation_titling.generate_conversation_title) that fires on a
    conversation's first message, reusing the same shared ai_provider
    instance as the chat answer. Confirms that extra call doesn't
    change which documents' content the first answer is grounded in --
    i.e. the AI provider being asked two different things
    (condense-or-generate + title) on the same first turn doesn't
    disturb retrieval or prompt construction for the actual answer.
    """
    ai_provider = AutoCondenseAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: DBMSKeywordEmbeddingProvider()
    client = TestClient(app)
    try:
        conversation_id, _function_doc_id, ddl_dml_doc_id = _two_document_conversation(client)

        first_turn = _send_message(
            client, conversation_id, "What is the difference between DDL and DML?"
        )
        assistant_message = first_turn["assistant_message"]

        assert assistant_message["grounded"] is True
        sources = assistant_message["sources"]
        assert any(source["document_id"] == ddl_dml_doc_id for source in sources)

        # The title call did happen (proving this test actually
        # exercises Phase 4's addition) and didn't replace/corrupt the
        # chat prompt.
        title_prompts = [p for p in ai_provider.prompts if "descriptive title" in p]
        assert len(title_prompts) == 1
        generation_prompt = ai_provider.chat_prompts[-1]
        assert f"— {DDL_DML_FILENAME}]" in generation_prompt

        detail = client.get(f"/api/v1/conversations/{conversation_id}")
        assert detail.json()["title"] == "DBMS Study Session"
        assert detail.json()["title_is_custom"] is False
    finally:
        app.dependency_overrides.clear()
