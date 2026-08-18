from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image

from app.services.ocr.ocr_engine_factory import get_ocr_engine

__all__ = ["extract_text", "extract_text_from_pdf"]


def extract_text(file_path: Path) -> str:
    """
    OCRs a single image file (.png, .jpg, .jpeg) and returns its text.

    Mirrors pdf_service.extract_text / docx_service.extract_text /
    pptx_service.extract_text's shape (one function, a `Path` in, a
    `str` out) so it can be registered in
    document_extraction_service._TEXT_EXTRACTORS exactly like they
    are — nothing about the dispatcher has to know this extractor
    runs an OCR engine instead of a format-specific parser.

    `image.load()` forces Pillow to fully decode the file rather than
    just read its header, so a truncated/corrupted image raises here
    -- same "a malformed file of the right type raises, and is caught
    by the upload route" contract pdf_service/docx_service/
    pptx_service already have for their own formats (see
    routes_documents.py's try/except around extraction).
    """
    with Image.open(file_path) as image:
        image.load()
        return _ocr_image(image)


def extract_text_from_pdf(file_path: Path) -> str:
    """
    OCRs a scanned PDF: one that has pages but no selectable text
    layer (photographed or scanned pages saved as a PDF). Called by
    document_extraction_service's PDF dispatch entry only after
    pdf_service.extract_text has already been tried and come back
    empty -- this function never decides *whether* to run, only *how*
    to extract once that decision has already been made.

    Renders every page to an image (pdf2image, backed by the
    `pdftoppm`/poppler binary already required for PDF handling in
    this environment) and OCRs each one, joining pages the same
    "blank line between pages" way pdf_service.extract_text does for
    a text PDF -- so a scanned and a text-layer PDF read identically
    to everything downstream.
    """
    pages = convert_from_path(str(file_path))
    engine = get_ocr_engine()
    pages_text = [_ocr_image(page, engine=engine) for page in pages]
    return "\n\n".join(pages_text).strip()


def _ocr_image(image: Image.Image, engine=None) -> str:
    engine = engine or get_ocr_engine()
    return engine.image_to_text(image).strip()
