from datetime import datetime

from pydantic import BaseModel

PREVIEW_LENGTH = 500


class DocumentResponse(BaseModel):
    """
    What the API sends back for a document. Note this is NOT the same
    shape as the Document DB model: we never send the full extracted
    text back here (it could be huge), just a preview and a count.
    Keeping the API schema separate from the DB model means we can
    change one without being forced to change the other.
    """

    id: str
    original_filename: str
    status: str
    created_at: datetime
    text_preview: str
    character_count: int

    # Lets Pydantic build this model directly from a SQLAlchemy object
    # (document.id, document.status, ...) instead of only from a dict.
    model_config = {"from_attributes": True}

    @staticmethod
    def from_document(document) -> "DocumentResponse":
        text = document.extracted_text or ""
        return DocumentResponse(
            id=document.id,
            original_filename=document.original_filename,
            status=document.status,
            created_at=document.created_at,
            text_preview=text[:PREVIEW_LENGTH],
            character_count=len(text),
        )
