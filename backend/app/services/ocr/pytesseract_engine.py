import pytesseract
from PIL import Image

from app.services.ocr.ocr_engine import OCREngine, OCREngineError


class PytesseractOCREngine(OCREngine):
    """
    OCREngine backed by Tesseract via pytesseract. pytesseract is a
    thin wrapper that shells out to the `tesseract` binary, which
    must be installed on the host — this class's only job is
    translating between OCREngine's interface and pytesseract's, and
    turning pytesseract's own exceptions into the one OCREngineError
    type every caller already knows how to handle.
    """

    def image_to_text(self, image: Image.Image) -> str:
        try:
            return pytesseract.image_to_string(image)
        except pytesseract.TesseractNotFoundError as exc:
            raise OCREngineError(
                "Tesseract is not installed or not on PATH."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise OCREngineError(f"Tesseract OCR failed: {exc}") from exc
