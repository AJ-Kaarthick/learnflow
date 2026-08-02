"""
The one place that knows "given a file extension, how do I turn that
file into plain text (and, if the format has one, a page count)".

    Document
       |
    document_extraction_service (this file)
       |-- pdf_service   (.pdf)
       |-- docx_service  (.docx)
       |
    Extracted text -> the existing LearnFlow pipeline (chunking,
    embeddings, RAG, summary, flashcards, quiz, mind map, chat), all
    of which only ever read `Document.extracted_text` and have no idea
    what file format it came from.

Adding a future format (PPTX, etc.) means writing one extractor module
with the same `extract_text(path) -> str` shape as pdf_service.py /
docx_service.py, and adding one line to `_TEXT_EXTRACTORS` below —
nothing in routes_documents.py or anywhere downstream has to change.
"""

from pathlib import Path
from typing import Callable

from app.services import docx_service, pdf_service

_TEXT_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".pdf": pdf_service.extract_text,
    ".docx": docx_service.extract_text,
}

# Only PDF has a well-defined, cheap-to-read page count (its page tree).
# A .docx file's page count depends on page size, margins, and fonts —
# it's a rendering/pagination outcome, not something stored in the file
# — so there's deliberately no docx entry here. Document.page_count is
# nullable for exactly this: formats without one just show nothing.
_PAGE_COUNTERS: dict[str, Callable[[Path], int]] = {
    ".pdf": pdf_service.get_page_count,
}


class UnsupportedFileTypeError(Exception):
    """Raised when asked to extract a file extension with no registered extractor."""


def is_supported_extension(extension: str) -> bool:
    return extension.lower() in _TEXT_EXTRACTORS


def extract_text(file_path: Path, extension: str) -> str:
    """
    Extracts a document's text using whichever extractor is registered
    for `extension` (e.g. ".pdf", ".docx"). Callers are expected to
    have already validated the extension (see ALLOWED_UPLOAD_TYPES in
    routes_documents.py) — this raises rather than guessing if they
    haven't, so an unsupported type fails loudly instead of silently
    producing no text.
    """
    extractor = _TEXT_EXTRACTORS.get(extension.lower())
    if extractor is None:
        raise UnsupportedFileTypeError(f"No text extractor registered for '{extension}' files.")
    return extractor(file_path)


def get_page_count(file_path: Path, extension: str) -> int | None:
    """
    Returns a page count for formats that have one, or None for
    formats that don't (currently just .docx) — same "nullable, shown
    as nothing" contract Document.page_count already documents for any
    document whose count can't be determined.
    """
    counter = _PAGE_COUNTERS.get(extension.lower())
    if counter is None:
        return None
    return counter(file_path)
