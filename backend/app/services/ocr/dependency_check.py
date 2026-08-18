"""
Checks for the OCR *system* dependencies pip can't install for us.

requirements.txt installs pytesseract and pdf2image, but those are
thin Python wrappers — they still need two real binaries present on
the host's PATH to actually do anything:

  - `tesseract`            (the OCR engine itself; pytesseract shells
                             out to it)
  - `pdftoppm` / `pdfinfo` (poppler's CLI tools; pdf2image shells out
                             to them to rasterize a PDF page to an
                             image before OCR can read it)

Neither is a Python package, so neither can go in requirements.txt —
they're OS-level installs (e.g. `apt install tesseract-ocr
poppler-utils`, or `brew install tesseract poppler`) that have to
happen outside pip entirely. A host that's missing one or both still
starts up fine and serves PDF/DOCX/PPTX requests fine (none of those
touch either binary) — only image and scanned-PDF processing is
affected, and until now it failed silently: every document extractor
funnels through the same generic `except Exception` in
routes_documents.py, so a missing binary looked identical to a
corrupted file, and the real reason never made it to the logs.

This module doesn't fix the missing binary — it can't, that's outside
the codebase — but it turns "silently fails per-document, with no way
to tell why" into "one clear warning in the logs the moment the
backend starts", so the actual cause is a log line away instead of a
guess.
"""

import shutil

import pytesseract


def check_ocr_dependencies() -> list[str]:
    """
    Returns a human-readable warning for each missing OCR system
    dependency, or an empty list if both are present. Never raises —
    a missing OCR dependency is a documented, expected startup state
    (PDF/DOCX/PPTX still work fully without either binary), not a
    reason to crash the app.
    """
    warnings: list[str] = []

    try:
        pytesseract.get_tesseract_version()
    except (pytesseract.TesseractNotFoundError, OSError):
        warnings.append(
            "OCR dependency missing: the 'tesseract' binary was not found on PATH. "
            "Image (.png/.jpg/.jpeg) and scanned-PDF processing will fail until it's "
            "installed (e.g. `apt install tesseract-ocr` or `brew install tesseract`). "
            "PDF/DOCX/PPTX processing is unaffected."
        )

    if shutil.which("pdftoppm") is None:
        warnings.append(
            "OCR dependency missing: poppler's 'pdftoppm' binary was not found on PATH. "
            "Scanned-PDF processing (PDFs with no selectable text layer) will fail until "
            "it's installed (e.g. `apt install poppler-utils` or `brew install poppler`). "
            "Normal (text-layer) PDF/DOCX/PPTX processing is unaffected."
        )

    return warnings
