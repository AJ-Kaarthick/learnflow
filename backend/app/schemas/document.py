from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator

PREVIEW_LENGTH = 500


class DocumentSortOption(str, Enum):
    """
    The 5 sort orders the Document Library supports. A str Enum so
    FastAPI validates the `sort` query param against exactly these
    values (invalid values -> automatic 422) and it serializes as a
    plain string, same as any other query param.
    """

    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    UPLOADED_NEWEST = "uploaded_newest"
    UPLOADED_OLDEST = "uploaded_oldest"
    RECENTLY_OPENED = "recently_opened"


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
    last_opened_at: datetime | None
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
            last_opened_at=document.last_opened_at,
            text_preview=text[:PREVIEW_LENGTH],
            character_count=len(text),
        )


class DocumentRenameRequest(BaseModel):
    """
    Body for PATCH /documents/{id}. Reuses the existing
    original_filename field as the editable display name rather than
    adding a separate column — same field the UI already shows.

    This only checks that the requested name isn't blank. Extension
    preservation happens in the route handler (see
    rename_document in routes_documents.py), not here, because it
    needs to know the document's *current* extension — which varies
    per document and per file type — and a field validator has no
    access to that.
    """

    original_filename: str

    @field_validator("original_filename")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped
