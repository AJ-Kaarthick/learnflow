from abc import ABC, abstractmethod

from PIL import Image


class OCREngineError(Exception):
    """
    Raised when an OCR engine fails to turn an image into text —
    missing/misconfigured OCR binary, an engine-level crash, whatever.
    Callers (ocr_service.py) catch this ONE exception type and never
    need to know or care which underlying engine (Tesseract today,
    something else later) raised it. Mirrors AIProviderError in
    app/services/ai/base_provider.py.
    """


class OCREngine(ABC):
    """
    The contract every OCR engine (Tesseract today, and later
    something like EasyOCR or a cloud OCR API) implements.
    Deliberately minimal: one method, an already-decoded image in,
    text out — mirrors AIProvider's "prompt in, text out" shape
    (app/services/ai/base_provider.py) for the same reason: swapping
    or adding an engine later is a new class behind this interface,
    not a change to ocr_service.py or anything upstream of it.

    Takes a PIL Image rather than a file path so the same engine
    implementation serves both callers in ocr_service.py: an image
    file opened directly, and a single rendered page of a scanned PDF
    (pdf2image.convert_from_path already returns a list of PIL
    Images) — neither caller has to round-trip through disk just to
    hand the engine something it can read.
    """

    @abstractmethod
    def image_to_text(self, image: Image.Image) -> str:
        """Runs OCR on a single in-memory image and returns its text."""
