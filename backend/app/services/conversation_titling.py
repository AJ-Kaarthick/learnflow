"""
Generates a short, descriptive title for a conversation from its first
user message, optionally informed by the filenames of whatever
documents are currently selected in the conversation (V2.4 Milestone 2
Phase 4 — automatic conversation naming, deliberately deferred from
Phase 3 until now — see Conversation's own docstring in db/models.py,
which already named this exact mechanism as "Milestone 3's
auto-titling"; document-filename context added in the Phase 4 naming
follow-up once "Inquiry regarding co..."-style generic titles showed
the first message alone often isn't enough to name a conversation).

Deliberately narrow scope, the same "one small, single-responsibility
module" precedent as query_condensation.py: this module's only job is
turning "first user message (+ optional document filenames)" into "a
short title string", or telling the caller it couldn't. It never
touches the database and knows nothing about
Conversation/title_is_custom/race protection — deciding *when* to call
this, persisting the result, and protecting a manual rename from ever
being overwritten are entirely routes_conversations.send_message's job
(see that function's own docstring for the full best-effort +
race-safety design). That split is what keeps this module reusable and
trivially testable in isolation, exactly like condense_query.

Filenames are the ONLY document signal this module accepts —
deliberately not extracted_text, a summary, or a retrieval call. The
first user message stays the primary signal; filenames are supporting
context for when the message alone doesn't establish a topic (see
_TITLE_INSTRUCTIONS' usage rules below). This keeps title generation
inside the single AI call it already made, with no new AI call, no new
DB fetch beyond what the caller already has loaded, and no new failure
mode — the existing best-effort "return None, never raise" contract is
unchanged and applies identically whether or not filenames are passed.
"""

from app.services.ai.base_provider import AIProvider, AIProviderError

# A title-quality backstop, not a validation error: the sidebar row
# this is shown in has limited width, and a model that ignores the
# prompt's own length instruction should still degrade to *something*
# reasonable rather than a paragraph-long title. Comfortably under
# MAX_TITLE_LENGTH (schemas/conversation.py, 200) — that constant
# bounds what a *human* can type into a manual rename; this is a much
# tighter, sidebar-appropriate target for an AI-generated one.
MAX_GENERATED_TITLE_LENGTH = 60

# The literal phrase "descriptive title" below is also what this
# project's test suite uses to tell a title-generation prompt apart
# from a normal chat-answer prompt when scripting a fake AIProvider
# (see tests/test_conversation_naming.py) — the same "recognize a call
# site by distinctive prompt text" technique
# test_conversational_retrieval.py's ScriptedAIProvider already uses
# for condense-vs-generate. Changing this wording is fine; just keep
# it distinctive from build_chat_prompt's and condense_query's own
# wording if so.
#
# The document-usage rules below exist specifically to prevent the two
# failure modes on either side of "ignore filenames entirely" (the old
# behavior, which produced content-free titles like "Inquiry regarding
# co..." for a vague first message): (1) mechanically prefixing/copying
# a filename into every title regardless of relevance, and (2) forcing
# every selected document's name into the title even when the message
# is only about one of them. "{documents_section}" is substituted with
# an empty string when there are no filenames to offer, so the prompt
# reads identically to the pre-Phase-4-naming-follow-up version for
# that case — no behavior change for a documentless call.
_TITLE_INSTRUCTIONS = (
    "Generate a short, descriptive title for a conversation that starts "
    "with the message below. The title will be shown in a sidebar next "
    "to titles of other conversations.\n\n"
    "Rules:\n"
    "- Output ONLY the title itself — no preamble, no quotation marks, "
    "no trailing punctuation, no explanation.\n"
    f"- Keep it under {MAX_GENERATED_TITLE_LENGTH} characters.\n"
    "- Describe the actual topic of the message, in plain, specific "
    "language.\n"
    "- Do not use generic wording like \"Conversation about...\" or "
    "\"New chat\".\n"
    "- Base the title primarily on the message itself — that is the "
    "main signal.\n"
    "- The selected document filenames below, if any, are context "
    "only, meant to help you figure out what the message is about when "
    "that isn't already obvious from the message alone. Never just "
    "copy, reformat, or prefix a filename into the title, and never "
    "list every filename.\n"
    "- If the message already makes the topic clear on its own, ignore "
    "the filenames and title it from the message.\n"
    "- If the message is vague (e.g. \"how many credits is this for\", "
    "\"what is this about\"), use a selected document's filename to "
    "infer the real-world subject it refers to, and title it around "
    "that subject — not around the filename text itself.\n"
    "- If several documents are selected but the message only concerns "
    "one of them (or its topic is self-contained), do not mention the "
    "other documents at all.\n"
    "- If the message genuinely compares or relates multiple selected "
    "documents, the title may reflect that comparison (e.g. \"X vs "
    "Y\").\n\n"
    "{documents_section}"
    "Message:\n{message}\n\n"
    "Title:"
)


def _format_documents_section(document_filenames: list[str] | None) -> str:
    """
    Renders the optional "selected documents" block substituted into
    _TITLE_INSTRUCTIONS' "{documents_section}" placeholder — empty
    string when there's nothing to offer (no documents, or a caller
    that doesn't pass any), so the prompt degrades to exactly its
    pre-filename-context wording for a documentless conversation.

    Deliberately just the filenames, one per line, with no summary or
    excerpt of their content — see this module's docstring for why
    filenames are the only document signal this module accepts.
    """
    if not document_filenames:
        return ""
    listed = "\n".join(f"- {filename}" for filename in document_filenames)
    return (
        "Documents currently selected in this conversation (context "
        "only — see the rules above for how to use these):\n"
        f"{listed}\n\n"
    )


def _build_title_prompt(first_message: str, document_filenames: list[str] | None = None) -> str:
    return _TITLE_INSTRUCTIONS.format(
        message=first_message,
        documents_section=_format_documents_section(document_filenames),
    )


def _sanitize(raw_title: str) -> str:
    """
    Strips wrapping quotes/whitespace a model might add despite being
    told not to (the same defensive stripping condense_query does for
    its own single-line output), collapses any internal newlines, and
    hard-truncates to MAX_GENERATED_TITLE_LENGTH.
    """
    cleaned = raw_title.strip()
    # Strip one layer of wrapping quotes, either style, if present.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()
    # Collapse whitespace/newlines into single spaces.
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > MAX_GENERATED_TITLE_LENGTH:
        cleaned = cleaned[:MAX_GENERATED_TITLE_LENGTH].rstrip()
    return cleaned


async def generate_conversation_title(
    first_message: str,
    ai_provider: AIProvider,
    document_filenames: list[str] | None = None,
) -> str | None:
    """
    Returns a short generated title for a new conversation based on
    its first user message, or None if generation wasn't possible —
    either the provider itself failed (AIProviderError) or its output
    was blank/unusable once sanitized.

    `document_filenames` is optional supporting context — the
    filenames of whatever documents are currently selected in the
    conversation, in any order, or None/empty if there are none (or
    the caller doesn't have any to offer). It's never required: this
    function's contract of "try once from the message, report whether
    it worked" is unchanged, and every existing caller/test that
    doesn't pass it gets the exact same prompt and behavior as before
    this parameter existed. When present, it's folded into the prompt
    as contextual filenames only (see _TITLE_INSTRUCTIONS) — never
    mechanically concatenated with the message, and the model is
    instructed to use it only to disambiguate a vague message, not to
    override a message that already states its own topic.

    Deliberately returns None instead of the raw first message or any
    other placeholder: unlike condense_query (where "fall back to the
    original question" is always a reasonable retrieval query on its
    own), there's no equally-good fallback *title* to invent here — the
    caller (routes_conversations.send_message) already has the right
    one: leave the conversation's existing default title exactly alone.
    This function's only job is "try once, report whether it worked" —
    it never raises for a provider failure, and never retries.
    """
    prompt = _build_title_prompt(first_message, document_filenames)

    try:
        raw_title = await ai_provider.generate_text(prompt)
    except AIProviderError:
        return None

    title = _sanitize(raw_title)
    return title or None
