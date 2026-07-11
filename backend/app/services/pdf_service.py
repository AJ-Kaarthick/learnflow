from pathlib import Path

from pypdf import PdfReader


def extract_text(file_path: Path) -> str:
    """
    Reads every page of a PDF and joins their text with blank lines
    between pages (helps the LLM later see where a page ended).

    Note: this only reads text that's already embedded in the PDF. A
    scanned PDF (pages that are really just photos) has no text layer,
    so this will return little or nothing for one. Handling that
    requires OCR, which is out of scope for V1 — see MILESTONE 1 notes.
    """
    reader = PdfReader(str(file_path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages_text).strip()
