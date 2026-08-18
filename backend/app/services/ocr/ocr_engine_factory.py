from app.core.config import settings
from app.services.ocr.ocr_engine import OCREngine
from app.services.ocr.pytesseract_engine import PytesseractOCREngine

# Adding a future engine (EasyOCR, a cloud OCR API, ...) later means:
# write one class implementing OCREngine, add one line here. Nothing
# else in the codebase changes — same registry pattern as _PROVIDERS
# in app/services/ai/provider_factory.py.
_OCR_ENGINES: dict[str, type[OCREngine]] = {
    "tesseract": PytesseractOCREngine,
}


def get_ocr_engine() -> OCREngine:
    """
    Returns the configured OCR engine. Called directly by
    ocr_service.py rather than via FastAPI's Depends() — document
    extraction as a whole (pdf_service, docx_service, pptx_service,
    and now this) is plain, synchronous, undecorated Python, invoked
    straight from routes_documents.py, not part of the request's
    dependency graph the way AIProvider/EmbeddingProvider are. Kept as
    its own function (rather than inlined in ocr_service.py) purely so
    a future test can swap it out the same way tests already fake
    AIProvider and EmbeddingProvider, without this module needing to
    change.
    """
    engine_class = _OCR_ENGINES.get(settings.ocr_engine)
    if engine_class is None:
        raise ValueError(
            f"Unknown OCR_ENGINE '{settings.ocr_engine}'. Available: {list(_OCR_ENGINES)}"
        )
    return engine_class()
