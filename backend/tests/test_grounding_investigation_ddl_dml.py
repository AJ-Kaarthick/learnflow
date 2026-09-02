"""
Forensic follow-up to a real, manually-reproduced retrieval failure
(see the investigation this test file documents):

    Selected: EX-DDL&DML.docx, EX-single row function.docx
    Turn 1: "What are these documents about? explain in detail" -> succeeds.
    Turn 2 (same conversation): "What is the difference between DDL
        and DML?" -> "I couldn't find the answer to this question in
        the uploaded document." with 8 sources shown.
    Turn 3: a paraphrase ("Explain DDL and DML and how they differ.")
        -> same failure.

A prior pass added test_conversation_retrieval_regression.py, which
proved the persisted-conversation WIRING is correct using a
content-sensitive embedding and a well-behaved ("cooperative") scripted
AI provider that always answers using whatever chunks it's given. That
is the right design for proving plumbing, but it can structurally never
catch THIS failure mode, because a cooperative fake by construction
never declines -- which is also, precisely, why none of the 355
pre-existing tests caught it either: every existing scripted AI
provider in this suite (ScriptedAIProvider, FakeAIProvider,
AutoCondenseAIProvider) is cooperative.

This file adds the missing piece: a forensic reconstruction of the
real two documents (see RECONSTRUCTION NOTES below), run through the
REAL, unmodified send_message -> answer_question -> condense_query ->
retrieve_relevant_chunks -> build_chat_prompt pipeline, instrumented
with a STRICT, non-cooperative scripted generator that mimics the
LETTER of the grounding prompt's own instruction ("Do not use any
outside knowledge, and do not guess or make anything up... If the
excerpts do not contain enough information to answer the question,
respond with exactly this sentence") -- answering a
"difference between DDL and DML"-style question only if a retrieved
excerpt contains an explicit definitional/contrastive sentence, not
merely the words "DDL"/"DML" in proximity (a document literally titled
"DDL and DML" will have both words in whichever chunk contains its
title regardless of retrieval quality, so that weaker check proves
nothing).

FINDING (see the investigation report for the full forensic trace):
with condensation behaving exactly per its documented contract
(returns an already-standalone follow-up unchanged) and with a content-
sensitive embedding that correctly, heavily favors the right document,
the final generation prompt DOES receive the correct DDL/DML content --
confirmed by direct inspection of the constructed prompt below -- and
the strict generator STILL declines, because the source text is a lab
exercise sheet (imperative instructions: "Create a table...", "Use
ALTER TABLE...", "Use INSERT INTO...") that never states a definitional
or contrastive sentence connecting DDL and DML. That is a property of
the CONTENT and of how conservatively a model applies its own
"don't guess" instruction to it -- not a defect in condensation,
retrieval, document-scope resolution, or prompt construction, all of
which are exercised and asserted correct below. See the investigation
report for why this is intentionally NOT "fixed" by loosening the
grounding prompt: that instruction is the entire anti-hallucination
safety mechanism, and weakening it to force this one query to pass
would trade a rare, safe "I don't know" for previously-prevented wrong
answers on every other query.

RECONSTRUCTION NOTES (what's confirmed vs. filler): confirmed present
in EX-DDL&DML.docx, from the real first successful answer's own
wording: tables named Student_Details and Employee_Details; columns
including Reg.no, Emp_name, Salary; ALTER TABLE used to add/drop/modify
columns and change data types; constraints NOT NULL, UNIQUE, CHECK,
PRIMARY KEY; INSERT INTO, UPDATE, DELETE; SELECT with WHERE, AND/OR,
IN, BETWEEN, ORDER BY, GROUP BY, HAVING, DISTINCT. Confirmed present in
EX-single row function.docx: date functions (months between dates,
rounding dates, truncating dates) and string functions (case
conversion, extracting characters, replacing characters). Exact
exercise wording/numbering is plausible filler, sized to a realistic
multi-page exercise sheet -- clearly an EXERCISE SHEET (numbered
imperative instructions), matching the "EX-" filename prefix, not
definitional prose.
"""

import io
import math
import re

import docx
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai.base_provider import AIProvider
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.ai.embedding_provider_factory import get_embedding_provider
from app.services.ai.provider_factory import get_ai_provider
from app.services.chat_service import NO_CONTEXT_ANSWER

DDL_DML_PARAGRAPHS = [
    "Exercise: DDL and DML Statements",
    "PART A - DDL",
    "1. Create a table named Student_Details with columns Reg_no (primary key, number), Name (varchar2, 30 characters), Department (varchar2, 20 characters), and Year (number). Use appropriate data types and sizes for each column as shown, and make sure Reg_no is declared as the primary key of the table at creation time.",
    "2. Create a table named Employee_Details with columns Emp_id (primary key, number), Emp_name (varchar2, 30 characters), Department (varchar2, 20 characters), and Salary (number, with two decimal places). This table will be used throughout the remaining DML and querying exercises below, so create it carefully before moving on.",
    "3. Use the ALTER TABLE command to add a new column called Email (varchar2, 40 characters) to the existing Student_Details table. Verify the new column has been added by describing the table structure afterward.",
    "4. Use the ALTER TABLE command to modify the data type and size of the Salary column in the Employee_Details table so that it can store larger values than originally defined. Describe the table again to confirm the change took effect.",
    "5. Use the ALTER TABLE command to add a NOT NULL constraint to the Name column of the Student_Details table, ensuring that every row must have a name value going forward.",
    "6. Add a UNIQUE constraint to the Reg_no column of the Student_Details table so that no two students can share the same registration number, even though it is already the primary key.",
    "7. Add a CHECK constraint to the Employee_Details table to ensure that the Salary column is always greater than zero for every row that is inserted or updated.",
    "8. Add a PRIMARY KEY constraint to the Emp_id column of the Employee_Details table if it was not already declared as the primary key when the table was first created.",
    "9. Use the ALTER TABLE command to drop a column from the Student_Details table, and confirm afterward that the column no longer appears when the table structure is described.",
    "PART B - DML",
    "10. Use the INSERT INTO command to add five new records to the Student_Details table, supplying realistic values for every column including Reg_no, Name, Department, Year, and Email.",
    "11. Use the INSERT INTO command to add three new records to the Employee_Details table, supplying realistic values for Emp_id, Emp_name, Department, and Salary.",
    "12. Use the UPDATE command to change the Department value for a specific student in the Student_Details table, identifying the row to update using its Reg_no in the WHERE clause.",
    "13. Use the UPDATE command to change the Salary value for a specific employee in the Employee_Details table, identifying the row to update using its Emp_id in the WHERE clause.",
    "14. Use the DELETE command to remove a record from the Student_Details table where the Reg_no matches a given value, and confirm the row was removed by querying the table afterward.",
    "15. Use the DELETE command to remove a record from the Employee_Details table where the Emp_id matches a given value, and confirm the row was removed by querying the table afterward.",
    "PART C - Querying and Data Retrieval",
    "16. Write a SELECT statement to retrieve all students in a given Department from the Student_Details table, using a WHERE clause to filter the results.",
    "17. Write a SELECT statement using the AND and OR logical operators to filter the Employee_Details table on two conditions at the same time, such as Department and a minimum Salary.",
    "18. Write a SELECT statement using the IN operator to match rows in the Employee_Details table against a list of Department values in a single condition.",
    "19. Write a SELECT statement using the BETWEEN operator to filter the Employee_Details table so that only rows with a Salary within a specified range are returned.",
    "20. Write a SELECT statement using ORDER BY to sort the Employee_Details table by Salary, both in ascending and descending order.",
    "21. Write a SELECT statement using GROUP BY together with HAVING to summarize the Salary column by Department, showing only departments whose average salary exceeds a given amount.",
    "22. Write a SELECT statement using DISTINCT to list the unique Department values that currently exist in the Employee_Details table.",
]

SINGLE_ROW_FUNCTION_PARAGRAPHS = [
    "Exercise: Single Row Functions",
    "PART A - Date Functions",
    "1. Write a query using MONTHS_BETWEEN to calculate the number of months between two given dates.",
    "2. Write a query using ROUND to round a date to the nearest month.",
    "3. Write a query using TRUNC to truncate a date to the start of the month.",
    "4. Write a query using ADD_MONTHS to add six months to a given date.",
    "5. Write a query using SYSDATE to display the current date.",
    "PART B - String Functions",
    "6. Write a query using UPPER to convert a string column to uppercase.",
    "7. Write a query using LOWER to convert a string column to lowercase.",
    "8. Write a query using SUBSTR to extract the first three characters of a string.",
    "9. Write a query using REPLACE to replace a character within a string.",
    "10. Write a query using LENGTH to find the length of a string.",
    "11. Write a query using CONCAT to join two strings.",
]

DDL_DML_FILENAME = "EX-DDL&DML.docx"
SINGLE_ROW_FUNCTION_FILENAME = "EX-single row function.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class TfIdfEmbeddingProvider(EmbeddingProvider):
    """
    A materially more realistic content-sensitive embedding fake than
    a hand-picked keyword classifier: vocabulary and IDF weights come
    from the real two-document corpus's own word/document frequencies,
    so shared vocabulary (table, write, query, using, column...) is
    automatically down-weighted while document-distinguishing
    vocabulary keeps its signal -- the general PRINCIPLE real
    embeddings exploit, without this fake being told in advance which
    words matter. `shared_baseline` adds one constant-valued dimension
    to every vector (query and document alike) to approximate the
    higher similarity floor real dense embeddings typically show
    between same-domain passages, which a sparse bag-of-words model
    otherwise understates -- see the investigation report for the
    empirical calibration.
    """

    def __init__(self, corpus_documents: list[str], shared_baseline: float = 40.0) -> None:
        vocab: dict[str, int] = {}
        doc_freq: dict[str, int] = {}
        for doc_text in corpus_documents:
            words_in_doc = set(re.findall(r"[a-z0-9_]+", doc_text.lower()))
            for word in words_in_doc:
                if word not in vocab:
                    vocab[word] = len(vocab)
                doc_freq[word] = doc_freq.get(word, 0) + 1
        n_docs = len(corpus_documents)
        self._vocab = vocab
        self._idf = {
            word: math.log((n_docs + 1) / (freq + 1)) + 1.0 for word, freq in doc_freq.items()
        }
        self._shared_baseline = shared_baseline

    def _vector_for(self, text: str) -> list[float]:
        vector = [0.0] * len(self._vocab)
        for word in re.findall(r"[a-z0-9_]+", text.lower()):
            idx = self._vocab.get(word)
            if idx is not None:
                vector[idx] += self._idf[word]
        vector.append(self._shared_baseline)
        return vector

    async def embed_document(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_query(self, text: str) -> list[float]:
        return self._vector_for(text)


class IdentityCondenseStrictLiteralAIProvider(AIProvider):
    """
    Condensation: returns the follow-up question literally unchanged --
    query_condensation.py's own documented contract for an
    already-standalone question, which both real failing questions
    were ("what is the difference between DDL and DML", "explain DDL
    and DML and how they differ" -- neither contains a pronoun or
    implicit reference). This rules OUT condensation drift as a
    variable: the test below proves the failure reproduces even with
    condensation behaving exactly as designed.

    Generation: answers a "difference between DDL and DML"-style
    question ONLY if a retrieved excerpt contains a SENTENCE with both
    "ddl" and "dml" together with a definitional/contrastive cue word
    ("stands for", "means", "define", "differ", "whereas", "structure",
    "manipulat"). Deliberately NOT satisfied by the two acronyms merely
    appearing near each other (e.g. in a document title) -- see module
    docstring for why that weaker check would prove nothing about a
    document literally named "DDL and DML".
    """

    _FOLLOW_UP_RE = re.compile(r"Follow-up question: (.*)\n\nStandalone query:", re.DOTALL)
    _EXCERPT_RE = re.compile(
        r"\[Excerpt \d+ — ([^\]]+)\]\n(.*?)(?=\n\n\[Excerpt|\n\nRecent conversation|\n\nQuestion:|\Z)",
        re.DOTALL,
    )
    _QUESTION_RE = re.compile(r"\nQuestion: (.*)\n\nAnswer:", re.DOTALL)
    _DEFINITIONAL_CUES = (
        "stands for",
        "means",
        "define",
        "definition",
        "differ",
        "whereas",
        "structure",
        "manipulat",
    )

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)

        if "Standalone query:" in prompt:
            match = self._FOLLOW_UP_RE.search(prompt)
            return match.group(1).strip() if match else ""

        if "descriptive title" in prompt:
            return "DBMS Exercises"

        return self._answer_strictly(prompt)

    def _answer_strictly(self, prompt: str) -> str:
        excerpts = self._EXCERPT_RE.findall(prompt)
        question_match = self._QUESTION_RE.search(prompt)
        question = question_match.group(1).strip() if question_match else ""
        lowered_q = question.lower()

        is_ddl_dml_comparison_question = (
            "ddl" in lowered_q
            and "dml" in lowered_q
            and any(cue in lowered_q for cue in ("differ", "how they", "compare"))
        )
        if not is_ddl_dml_comparison_question:
            filenames = sorted({filename for filename, _ in excerpts})
            return "These documents cover: " + "; ".join(filenames)

        for filename, content in excerpts:
            for sentence in re.split(r"(?<=[.!?])\s+", content):
                lowered_sentence = sentence.lower()
                mentions_both = "ddl" in lowered_sentence and "dml" in lowered_sentence
                has_definitional_cue = any(
                    cue in lowered_sentence for cue in self._DEFINITIONAL_CUES
                )
                if mentions_both and has_definitional_cue:
                    return f"Based on {filename}: {sentence.strip()}"
        return NO_CONTEXT_ANSWER

    @property
    def chat_prompts(self) -> list[str]:
        return [
            p for p in self.prompts if "Standalone query:" not in p and "descriptive title" not in p
        ]


def test_strict_literal_grounding_declines_on_procedural_content_despite_correct_retrieval():
    """
    The forensic reproduction: proves retrieval, condensation, document
    scope, and prompt construction all correctly deliver the DDL/DML
    content on turn 2 of a real, persisted, multi-document conversation
    -- and that a strict, literal grounding decision can still decline
    on that correctly-delivered content, because the source text is
    procedural (exercise instructions) rather than definitional prose.
    This is the actual failure mechanism behind the real browser
    reproduction, not a stand-in for it.
    """
    ai_provider = IdentityCondenseStrictLiteralAIProvider()
    corpus = [" ".join(DDL_DML_PARAGRAPHS), " ".join(SINGLE_ROW_FUNCTION_PARAGRAPHS)]
    embedding_provider = TfIdfEmbeddingProvider(corpus)

    app.dependency_overrides[get_ai_provider] = lambda: ai_provider
    app.dependency_overrides[get_embedding_provider] = lambda: embedding_provider
    client = TestClient(app)
    try:
        ddl_dml_upload = client.post(
            "/api/v1/documents/upload",
            files={"file": (DDL_DML_FILENAME, _make_docx_bytes(DDL_DML_PARAGRAPHS), DOCX_MIME)},
        )
        assert ddl_dml_upload.status_code == 201, ddl_dml_upload.text
        ddl_dml_id = ddl_dml_upload.json()["id"]
        assert client.post(f"/api/v1/documents/{ddl_dml_id}/index").status_code == 201

        function_upload = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    SINGLE_ROW_FUNCTION_FILENAME,
                    _make_docx_bytes(SINGLE_ROW_FUNCTION_PARAGRAPHS),
                    DOCX_MIME,
                )
            },
        )
        assert function_upload.status_code == 201, function_upload.text
        function_id = function_upload.json()["id"]
        assert client.post(f"/api/v1/documents/{function_id}/index").status_code == 201

        conversation = client.post(
            "/api/v1/conversations", json={"document_ids": [function_id, ddl_dml_id]}
        )
        assert conversation.status_code == 201
        conversation_id = conversation.json()["id"]

        # Turn 1: the broad question from the real reproduction. Succeeds.
        turn1 = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "What are these documents about? explain in detail"},
        )
        assert turn1.status_code == 201
        assert turn1.json()["assistant_message"]["grounded"] is True

        # Turn 2: the exact real failing question, same conversation.
        turn2 = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "What is the difference between DDL and DML?"},
        )
        assert turn2.status_code == 201
        assistant_message = turn2.json()["assistant_message"]

        # --- Condensation correctly preserved intent (ruling out A) ---
        condense_prompts = [p for p in ai_provider.prompts if "Standalone query:" in p]
        assert len(condense_prompts) == 1
        follow_up_match = IdentityCondenseStrictLiteralAIProvider._FOLLOW_UP_RE.search(
            condense_prompts[0]
        )
        assert follow_up_match.group(1).strip() == "What is the difference between DDL and DML?"

        # --- Retrieval correctly, heavily favored the right document
        #     (ruling out B/C as the primary cause) ---
        generation_prompt = ai_provider.chat_prompts[-1]
        excerpt_matches = IdentityCondenseStrictLiteralAIProvider._EXCERPT_RE.findall(
            generation_prompt
        )
        ddl_dml_excerpt_count = sum(
            1 for filename, _ in excerpt_matches if filename == DDL_DML_FILENAME
        )
        assert ddl_dml_excerpt_count >= 4, (
            f"expected the DDL/DML document to dominate retrieved excerpts, got "
            f"{ddl_dml_excerpt_count} of {len(excerpt_matches)} from {DDL_DML_FILENAME!r}"
        )

        # --- The correct content reached the generation prompt
        #     (ruling out D) ---
        assert f"— {DDL_DML_FILENAME}]" in generation_prompt
        assert "ddl" in generation_prompt.lower()
        assert "dml" in generation_prompt.lower()
        assert "CREATE" in generation_prompt or "ALTER TABLE" in generation_prompt
        assert "INSERT INTO" in generation_prompt or "UPDATE" in generation_prompt

        # --- THE ACTUAL FAILURE: a strict, literal grounding decision
        #     still declines on this correctly-delivered content,
        #     because it's procedural, not definitional (E/F, not a
        #     code defect -- H holds for every upstream stage) ---
        assert assistant_message["content"] == NO_CONTEXT_ANSWER
        sources = assistant_message["sources"] or []
        assert sources, "sources were still returned even though the answer declined -- matches the real report's '8 sources' symptom"
        assert any(source["document_id"] == ddl_dml_id for source in sources)
    finally:
        app.dependency_overrides.clear()
