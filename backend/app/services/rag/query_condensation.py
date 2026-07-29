"""
Turns a possibly-ambiguous follow-up question ("Explain it.", "Compare
it with the second document.") plus recent conversation history into a
standalone, self-contained query suitable for embedding-based
retrieval.

This is the piece Milestone 5's diagnosis identified as missing:
retrieval only ever saw the literal current-turn question text (see
retrieval_service.py), so a follow-up whose meaning depends on prior
turns ("it", "that", "the second one", "tell me more") could retrieve
chunks unrelated to what the user is actually asking about, even
though the *generation* step already had enough conversational context
to understand the reference.

Deliberately narrow, single-responsibility module: its only job is
producing better input to retrieve_relevant_chunks(). It never answers
the user's question, never asserts a fact, and its output is never
shown to the user or used as grounding for the final answer — that
separation is what lets this addition improve retrieval without
touching hallucination prevention at all. chat_service.build_chat_prompt
still receives the user's original question and original history,
completely unchanged; condensation only affects what text gets
embedded and searched for.

Kept in app/services/rag/ alongside chunking.py, embedding_service.py,
and retrieval_service.py: like them, this is generic to "retrieval
over documents", not specific to chat, so any future feature that
needs history-aware retrieval (e.g. a future tutor mode) can reuse it
the same way chat_service does, without depending on chat_service
itself.
"""

from app.services.ai.base_provider import AIProvider, AIProviderError

# One prior turn: {"role": "user" | "assistant", "content": str}. Same
# shape as chat_service.HistoryTurn (duplicated here rather than
# imported to keep this module independent of chat_service — retrieval
# concerns should not need to import from the feature that happens to
# be their first caller today).
HistoryTurn = dict[str, str]

# Distinct from chat_service.NO_CONTEXT_ANSWER's framing on purpose:
# this prompt's only job is to resolve references using history, never
# to add information history doesn't already make explicit. Asking the
# model to "preserve intent exactly" and "do not add information" is
# what keeps a condensation mistake from turning into a hallucination
# risk — the worst case of a bad rewrite is a query that retrieves
# poorly (the Milestone 5 status quo), not one that invents facts,
# since the rewritten text is never shown to the user or treated as an
# answer.
_CONDENSE_INSTRUCTIONS = (
    "Rewrite the follow-up question below as a single, standalone "
    "search query that makes sense with no prior context, by resolving "
    "any pronouns or implicit references (\"it\", \"that\", \"the "
    "second one\", \"tell me more\") using the conversation so far.\n\n"
    "Rules:\n"
    "- Output ONLY the rewritten query and nothing else — no preamble, "
    "no quotation marks, no explanation.\n"
    "- Do not answer the question.\n"
    "- Do not add any information, facts, or assumptions beyond what "
    "the conversation already makes explicit.\n"
    "- Preserve the user's actual scope and intent exactly (e.g. don't "
    "turn a question about one document into one about all of them).\n"
    "- If the follow-up question is already standalone and doesn't "
    "depend on the conversation, return it unchanged.\n\n"
)


def _format_history(history: list[HistoryTurn]) -> str:
    return "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in history)


def _build_condense_prompt(question: str, history: list[HistoryTurn]) -> str:
    return (
        f"{_CONDENSE_INSTRUCTIONS}"
        f"Conversation so far:\n{_format_history(history)}\n\n"
        f"Follow-up question: {question}\n\n"
        "Standalone query:"
    )


async def condense_query(
    question: str,
    history: list[HistoryTurn],
    ai_provider: AIProvider,
) -> str:
    """
    Returns a standalone version of `question` for retrieval purposes,
    using `history` to resolve references.

    Skips the AI call entirely — returning `question` unchanged — when
    there's no history to resolve against. This matters for two
    reasons: it keeps a fresh conversation's first turn exactly as fast
    and as cheap as it was before this milestone (no regression for
    the common case), and it means "nothing to condense" can never be
    misread by the model as "condense this into something unrelated".

    Also falls back to `question` unchanged if the AI call itself
    fails (AIProviderError) or returns something unusable (blank after
    stripping). Retrieval always gets *some* non-empty query this way —
    never an exception, never an empty string — so a condensation
    failure degrades gracefully to Milestone 5's raw-question behavior
    instead of breaking the chat request outright.
    """
    if not history:
        return question

    prompt = _build_condense_prompt(question, history)

    try:
        rewritten = await ai_provider.generate_text(prompt)
    except AIProviderError:
        return question

    rewritten = rewritten.strip().strip('"')
    return rewritten or question
