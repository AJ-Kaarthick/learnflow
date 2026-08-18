"""
The one place that knows "given a file extension, how do I turn that
file into plain text (and, if the format has one, a page count)".

    Document
       |
    document_extraction_service (this file)
       |-- pdf_service   (.pdf, when it has a selectable text layer)
       |-- docx_service  (.docx)
       |-- pptx_service  (.pptx)
       |-- ocr_service   (.png / .jpg / .jpeg, and .pdf when it doesn't)
       |
    Extracted text -> the existing LearnFlow pipeline (chunking,
    embeddings, RAG, summary, flashcards, quiz, mind map, chat), all
    of which only ever read `Document.extracted_text` and have no idea
    what file format it came from, or whether OCR was involved in
    producing it.

Adding a future format means writing one extractor module with the
same `extract_text(path) -> str` shape as pdf_service.py /
docx_service.py / pptx_service.py / ocr_service.py, and adding one
line to `_TEXT_EXTRACTORS` below — nothing in routes_documents.py or
anywhere downstream has to change.

PDF is the one entry in `_TEXT_EXTRACTORS` that isn't a single
service's `extract_text` directly. A PDF may or may not have a
selectable text layer -- a normal PDF does, a scanned/photographed one
doesn't -- and that's not something the file extension or upload
content-type can tell you, only the file's own content can. So
`_extract_pdf_text` below *is* the dispatcher this milestone asks for:
it tries pdf_service (cheap, and correct for the common case), and
only reaches for ocr_service -- convert each page to an image, OCR it
-- when that comes back with no selectable text. Everything else about
the two paths (module boundaries, the `extract_text(path) -> str`
shape, being just another `_TEXT_EXTRACTORS` entry) stays identical.
"""

from pathlib import Path
from typing import Callable

from app.services import docx_service, ocr_service, pdf_service, pptx_service


def _extract_pdf_text(file_path: Path) -> str:
    """
    Tries normal PDF text extraction first. If the PDF has no
    selectable text at all -- a scanned or photographed PDF, which
    pdf_service.extract_text already documents as returning "little or
    nothing" for -- falls back to OCR (see ocr_service.extract_text_from_pdf),
    which renders each page to an image and reads it that way instead.
    """
    text = pdf_service.extract_text(file_path)
    if text.strip():
        return text
    return ocr_service.extract_text_from_pdf(file_path)


_TEXT_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".pdf": _extract_pdf_text,
    ".docx": docx_service.extract_text,
    ".pptx": pptx_service.extract_text,
    ".png": ocr_service.extract_text,
    ".jpg": ocr_service.extract_text,
    ".jpeg": ocr_service.extract_text,
}

# Only PDF has a well-defined, cheap-to-read page count (its page tree)
# -- and that's still true whether or not that PDF ended up going
# through OCR; _extract_pdf_text above only changes how the *text* is
# obtained, never what "a page" means for a PDF, so .pdf keeps exactly
# one page-counter entry either way. A .docx file's page count depends
# on page size, margins, and fonts — it's a rendering/pagination
# outcome, not something stored in the file — so there's deliberately
# no docx entry here. A .pptx file has a slide *count*, not a page
# count, and that's a different concept the UI already handles by
# falling back to a file-type label (see DocumentList.jsx's
# formatPageCountOrFileType) — so pptx is left out here too,
# deliberately, same as docx. A single image (.png/.jpg/.jpeg) has no
# concept of "pages" at all, so it's left out for the same reason.
# Document.page_count is nullable for exactly this: formats without
# one just show nothing.
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
