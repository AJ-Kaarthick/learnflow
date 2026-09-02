"""
Tests for app/services/conversation_titling.py (V2.4 Milestone 2
Phase 4 -- automatic conversation naming) in isolation -- fast, no
HTTP, no database, the same "layer 1" precedent
test_conversational_retrieval.py already established for
condense_query(). What happens when this is actually wired into
POST /conversations/{id}/messages (when it's called, the race
protection around writing the result, best-effort failure handling at
the route level) is covered separately in test_conversation_naming.py.
"""

import asyncio

from app.services.ai.base_provider import AIProvider, AIProviderError
from app.services.conversation_titling import (
    MAX_GENERATED_TITLE_LENGTH,
    generate_conversation_title,
)


class ScriptedTitleProvider(AIProvider):
    """Returns a fixed string (or raises) and records every prompt it was called with."""

    def __init__(self, title: str | None = None, raise_error: bool = False) -> None:
        self._title = title
        self._raise_error = raise_error
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self._raise_error:
            raise AIProviderError("Simulated provider failure.")
        return self._title

    @property
    def last_prompt(self) -> str | None:
        return self.prompts[-1] if self.prompts else None


# --- happy path ---------------------------------------------------------


def test_generate_title_returns_sanitized_provider_output():
    provider = ScriptedTitleProvider(title="Photosynthesis Basics")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result == "Photosynthesis Basics"


def test_generate_title_prompt_includes_the_first_message():
    provider = ScriptedTitleProvider(title="Photosynthesis Basics")
    asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert "What is photosynthesis?" in provider.last_prompt


def test_generate_title_prompt_forbids_generic_wording_and_quotes():
    """
    Title-quality requirements from the brief (concise, no unnecessary
    quotation marks, no "Conversation about..." wording, no
    explanations) are enforced by *instructing* the model, not by
    post-hoc rejecting an output that ignores them -- confirms the
    instructions asking for that are actually present in the prompt.
    """
    provider = ScriptedTitleProvider(title="Photosynthesis Basics")
    asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    prompt = provider.last_prompt
    assert "no quotation marks" in prompt
    assert "Conversation about" in prompt
    assert "no explanation" in prompt


# --- document filenames as context (naming follow-up) ---------------------
#
# These tests exercise the *prompt construction*, not real title quality --
# ScriptedTitleProvider returns a fixed canned title no matter what it's
# asked, exactly like the tests above it. What's being verified here is
# that (a) filenames actually reach the prompt when given, (b) they don't
# when omitted (backward compatibility with every call site/test that
# predates this parameter), and (c) the prompt's own instructions tell the
# model how to use them -- the same "instruct, don't post-filter"
# philosophy as the generic-wording test above.


def test_generate_title_prompt_has_no_documents_section_when_none_given():
    """
    The default, parameter-omitted call -- what every pre-existing test in
    this file above still does -- must produce the exact same prompt shape
    as before this parameter existed: no "selected documents" section at
    all.
    """
    provider = ScriptedTitleProvider(title="Photosynthesis Basics")
    asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert "selected in this conversation" not in provider.last_prompt


def test_generate_title_prompt_has_no_documents_section_for_empty_list():
    provider = ScriptedTitleProvider(title="Photosynthesis Basics")
    asyncio.run(
        generate_conversation_title(
            "What is photosynthesis?", provider, document_filenames=[]
        )
    )
    assert "selected in this conversation" not in provider.last_prompt


def test_generate_title_prompt_includes_a_single_document_filename():
    provider = ScriptedTitleProvider(title="Timetable Credit Inquiry")
    asyncio.run(
        generate_conversation_title(
            "how many credits is this for",
            provider,
            document_filenames=["Timetable final 1.pdf"],
        )
    )
    assert "Timetable final 1.pdf" in provider.last_prompt


def test_generate_title_prompt_includes_every_filename_for_multiple_documents():
    provider = ScriptedTitleProvider(title="Timetable vs Serverless Computing")
    asyncio.run(
        generate_conversation_title(
            "how do the documents differ from each other?",
            provider,
            document_filenames=[
                "Timetable final 1.pdf",
                "Module_01_serverless_computing_Lec01.pptx",
            ],
        )
    )
    prompt = provider.last_prompt
    assert "Timetable final 1.pdf" in prompt
    assert "Module_01_serverless_computing_Lec01.pptx" in prompt


def test_generate_title_prompt_instructs_filenames_as_context_only():
    """
    Confirms the actual usage rules the naming follow-up added are present
    in the prompt whenever filenames are given -- not just the filenames
    themselves. This is what's meant to stop the model from mechanically
    concatenating a filename onto the title or forcing every selected
    document into it.
    """
    provider = ScriptedTitleProvider(title="Timetable Credit Inquiry")
    asyncio.run(
        generate_conversation_title(
            "how many credits is this for",
            provider,
            document_filenames=["Timetable final 1.pdf"],
        )
    )
    prompt = provider.last_prompt
    assert "context only" in prompt
    assert "never list every filename" in prompt
    assert "Base the title primarily on the message itself" in prompt


def test_generate_title_prompt_still_includes_message_when_documents_given():
    """The message stays present (and the primary signal) even once filenames are added."""
    provider = ScriptedTitleProvider(title="Timetable Credit Inquiry")
    asyncio.run(
        generate_conversation_title(
            "how many credits is this for",
            provider,
            document_filenames=["Timetable final 1.pdf"],
        )
    )
    assert "how many credits is this for" in provider.last_prompt


# --- sanitization ---------------------------------------------------------


def test_generate_title_strips_wrapping_double_quotes():
    provider = ScriptedTitleProvider(title='"Photosynthesis Basics"')
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result == "Photosynthesis Basics"


def test_generate_title_strips_wrapping_single_quotes():
    provider = ScriptedTitleProvider(title="'Photosynthesis Basics'")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result == "Photosynthesis Basics"


def test_generate_title_strips_surrounding_whitespace_and_newlines():
    provider = ScriptedTitleProvider(title="\n  Photosynthesis Basics  \n")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result == "Photosynthesis Basics"


def test_generate_title_collapses_internal_whitespace():
    provider = ScriptedTitleProvider(title="Photosynthesis   and\n\nChlorophyll")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result == "Photosynthesis and Chlorophyll"


def test_generate_title_truncates_titles_longer_than_the_limit():
    long_title = "Photosynthesis " * 20  # far past MAX_GENERATED_TITLE_LENGTH
    provider = ScriptedTitleProvider(title=long_title)
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result is not None
    assert len(result) <= MAX_GENERATED_TITLE_LENGTH


# --- invalid/unusable output handled safely --------------------------


def test_generate_title_returns_none_for_blank_output():
    provider = ScriptedTitleProvider(title="   ")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result is None


def test_generate_title_returns_none_for_empty_string_output():
    provider = ScriptedTitleProvider(title="")
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result is None


def test_generate_title_returns_none_for_quote_only_output():
    provider = ScriptedTitleProvider(title='""')
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result is None


# --- provider failure ---------------------------------------------------


def test_generate_title_returns_none_on_provider_error():
    """
    Best-effort at the service level: a provider failure must degrade
    to None, never raise -- the caller (routes_conversations.send_message)
    depends on this to keep title generation from ever failing the
    surrounding chat request.
    """
    provider = ScriptedTitleProvider(raise_error=True)
    result = asyncio.run(generate_conversation_title("What is photosynthesis?", provider))
    assert result is None
