"""
Orchestrates a single grounded question-answer turn over one document:
retrieve relevant chunks (retrieval_service.py, unchanged), build a
prompt that restricts the model to only that context, and generate an
answer (AIProvider, unchanged).

Deliberately thin: this module owns exactly one new thing — turning
"chunks + a question" into a grounded prompt — and reuses everything
else. Retrieval and generation stay separate responsibilities (this
file calls both, but is neither): retrieve_relevant_chunks() still
knows nothing about chat, and AIProvider still knows nothing about
where its prompt's context came from.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Document
from app.services.ai.base_provider import AIProvider
from app.services.ai.embedding_provider import EmbeddingProvider
from app.services.rag.retrieval_service import DEFAULT_TOP_K, ScoredChunk, retrieve_relevant_chunks

# Returned verbatim when there's no context to answer from at all (see
# answer_question below), and also given to the model as the exact
# sentence to use when retrieved context doesn't answer the question
# (see build_chat_prompt). One fixed string for both paths means a
# caller sees the same "not in the document" phrase regardless of
# which of the two produced it.
NO_CONTEXT_ANSWER = "I couldn't find the answer to this question in the uploaded document."


@dataclass
class ChatAnswer:
    answer: str
    chunks: list[ScoredChunk]
    # False only when there was no retrieved context at all to ground
    # an answer in (see answer_question). True whenever the model was
    # actually called with context — including when that context
    # wasn't enough and the model said so via NO_CONTEXT_ANSWER; that
    # is a grounded answer (the model correctly reported what the
    # document does or doesn't say), just not a positive one.
    grounded: bool


def build_chat_prompt(question: str, chunks: list[ScoredChunk]) -> str:
    context = "\n\n".join(
        f"[Excerpt {index + 1}]\n{scored.chunk.content}"
        for index, scored in enumerate(chunks)
    )
    return (
        "You are answering a student's question about a document, using "
        "ONLY the excerpts below. Do not use any outside knowledge, and do "
        "not guess or make anything up. If the excerpts do not contain "
        "enough information to answer the question, respond with exactly "
        f'this sentence and nothing else: "{NO_CONTEXT_ANSWER}"\n\n'
        f"Document excerpts:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


async def answer_question(
    document: Document,
    question: str,
    db: Session,
    ai_provider: AIProvider,
    embedding_provider: EmbeddingProvider,
    top_k: int = DEFAULT_TOP_K,
) -> ChatAnswer:
    """
    Retrieves the chunks most relevant to `question` and asks the AI
    provider to answer using only those chunks.

    Single-document today by design (`document`, not `document_ids`) —
    matching this milestone's scope. Multi-document chat would extend
    retrieve_relevant_chunks() (or add a sibling that queries across
    several document ids) and this function's `document` parameter
    would become a list; the prompt-building and grounding logic below
    wouldn't need to change.
    """
    chunks = await retrieve_relevant_chunks(
        document_id=document.id,
        query=question,
        db=db,
        embedding_provider=embedding_provider,
        top_k=top_k,
    )

    if not chunks:
        # No indexed chunks for this document at all — there's no
        # context an AI call could possibly ground an answer in, so
        # skip the call rather than risk it answering from outside
        # knowledge. (Routes should generally reject un-indexed
        # documents before this is ever reached — see routes_chat.py —
        # but this keeps the service itself safe to call directly too.)
        return ChatAnswer(answer=NO_CONTEXT_ANSWER, chunks=[], grounded=False)

    prompt = build_chat_prompt(question, chunks)
    answer = await ai_provider.generate_text(prompt)

    return ChatAnswer(answer=answer.strip(), chunks=chunks, grounded=True)
