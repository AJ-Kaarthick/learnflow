import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, DocumentChunk, Flashcard, MindMap, QuizQuestion, Summary
from app.schemas.document import DocumentRenameRequest, DocumentResponse, DocumentSortOption
from app.services import document_extraction_service, storage_service
from app.utils import filenames

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# Maps an accepted upload content-type to the file extension it means.
# The extension drives everything downstream of validation — what gets
# saved to disk (storage_service.save_uploaded_file) and which
# extractor runs (document_extraction_service.extract_text) — rather
# than trusting whatever the original filename happens to end in.
#
# Adding a future format is one new entry here, matched by one new
# extractor registered in document_extraction_service.py.
ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "image/png": ".png",
    # Browsers report the same content-type, "image/jpeg", for both a
    # .jpg and a .jpeg upload -- there's no wire-level distinction
    # between the two extensions, only ever a filename convention. One
    # canonical stored extension is picked here (matching the ".jpg"
    # this maps to), the same way every other entry in this dict picks
    # one canonical extension per content-type; document_extraction_service
    # also registers ".jpeg" in its own dispatch table (routed to the
    # same ocr_service.extract_text as ".jpg") purely so a document
    # whose *original_filename* happens to end in ".jpeg" -- e.g. after
    # a rename, which derives its extension from original_filename, not
    # from this dict -- still dispatches correctly.
    "image/jpeg": ".jpg",
}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _escape_like(value: str) -> str:
    """
    Escapes LIKE/ILIKE wildcard characters so a search for a literal
    "%" or "_" doesn't get treated as a wildcard. Paired with
    `.ilike(..., escape="\\")` below.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    search: str | None = Query(default=None, description="Case-insensitive, partial filename match."),
    sort: DocumentSortOption = Query(default=DocumentSortOption.UPLOADED_NEWEST),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """
    The Document Library list. Filtering and sorting both happen here,
    in the database query, rather than in the frontend — search and
    sort are the same "which documents, in what order" question the
    DB is already best suited to answer, and it keeps that logic in
    one tested place instead of duplicated in JS.
    """
    query = db.query(Document)

    search = (search or "").strip()
    if search:
        query = query.filter(
            Document.original_filename.ilike(f"%{_escape_like(search)}%", escape="\\")
        )

    if sort == DocumentSortOption.NAME_ASC:
        query = query.order_by(func.lower(Document.original_filename).asc())
    elif sort == DocumentSortOption.NAME_DESC:
        query = query.order_by(func.lower(Document.original_filename).desc())
    elif sort == DocumentSortOption.UPLOADED_OLDEST:
        query = query.order_by(Document.created_at.asc())
    elif sort == DocumentSortOption.RECENTLY_OPENED:
        # Never-opened documents have a null last_opened_at, which
        # sorts last here — falling back to upload recency among them
        # so the list still has a sensible order for documents that
        # have never been opened.
        query = query.order_by(Document.last_opened_at.desc(), Document.created_at.desc())
    else:  # UPLOADED_NEWEST, the default
        query = query.order_by(Document.created_at.desc())

    documents = query.all()
    return [DocumentResponse.from_document(document) for document in documents]


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> DocumentResponse:
    extension = ALLOWED_UPLOAD_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, DOCX, PPTX, PNG, JPG, and JPEG files are accepted.",
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 20 MB limit.")

    stored_filename = storage_service.save_uploaded_file(file_bytes, extension=extension)

    # Save a record immediately, before extraction runs, so that even
    # if extraction fails we still know the upload happened and can
    # show a "failed" status instead of losing the record entirely.
    document = Document(
        original_filename=file.filename,
        stored_filename=stored_filename,
        status="processing",
        # Known as soon as the bytes are in hand — no need to wait for
        # extraction or stat the file back off disk.
        file_size_bytes=len(file_bytes),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        stored_path = storage_service.get_path(stored_filename)
        # Dispatches to the right extractor (PDF, DOCX, ...) for this
        # document's extension — see document_extraction_service.py.
        # A corrupted or malformed file of the right type (e.g. a
        # truncated/invalid .docx) raises here, same as it always has
        # for PDFs, and is handled the same way: caught below, and
        # surfaced as a "failed" status rather than a 500.
        text = document_extraction_service.extract_text(stored_path, extension)
        document.extracted_text = text
        document.page_count = document_extraction_service.get_page_count(stored_path, extension)
        document.status = "ready"
    except Exception:
        # Previously this swallowed the exception entirely — a
        # malformed file and a missing OCR system dependency (see
        # ocr/dependency_check.py) both landed here and looked
        # identical from the logs, because nothing was logged at all.
        # logger.exception captures the real exception type, message,
        # and traceback, so "why did this document fail" is answered
        # by the logs instead of by guessing. The document's own
        # status still becomes "failed" either way — that part of the
        # contract (and everything downstream that depends on it,
        # like chat's "not ready for indexing" guard) is unchanged.
        logger.exception(
            "Document processing failed: id=%s filename=%r extension=%r",
            document.id,
            document.original_filename,
            extension,
        )
        document.status = "failed"

    db.commit()
    db.refresh(document)

    return DocumentResponse.from_document(document)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentResponse:
    document = db.query(Document).filter(Document.id == document_id).first()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return DocumentResponse.from_document(document)


@router.post("/{document_id}/open", response_model=DocumentResponse)
def mark_document_opened(document_id: str, db: Session = Depends(get_db)) -> DocumentResponse:
    """
    Called whenever the user opens a document from the library, purely
    to timestamp it for the "Recently Opened" sort — this endpoint has
    no other side effects and doesn't touch the document's content.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    document.last_opened_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)

    return DocumentResponse.from_document(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
def rename_document(
    document_id: str, payload: DocumentRenameRequest, db: Session = Depends(get_db)
) -> DocumentResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    # The extension is whatever this specific document's current name
    # already ends in (".pdf" today, but ".docx"/".pptx"/".png"/etc.
    # once other file types are supported) -- never a hardcoded
    # constant. Renaming can only change the text in front of it: any
    # extension-looking suffix the caller sends is stripped off (if it
    # matches) or otherwise kept as literal text in the base name, and
    # the document's real extension is reapplied either way.
    extension = filenames.get_extension(document.original_filename)
    base_name = filenames.strip_extension(payload.original_filename, extension).strip()
    if not base_name:
        raise HTTPException(status_code=422, detail="Name cannot be empty.")
    if not any(character.isalnum() for character in base_name):
        raise HTTPException(
            status_code=422, detail="Name must include at least one letter or number."
        )

    new_filename = f"{base_name}{extension}"

    # Case-insensitive, whitespace-insensitive duplicate check against
    # every *other* document. func.trim() guards against any legacy
    # row whose name has stray leading/trailing whitespace (upload
    # doesn't trim file.filename), so the comparison is symmetric with
    # how new_filename was just built.
    duplicate = (
        db.query(Document)
        .filter(Document.id != document_id)
        .filter(func.lower(func.trim(Document.original_filename)) == new_filename.lower())
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f'A document named "{new_filename}" already exists. Choose a different name.',
        )

    document.original_filename = new_filename
    db.commit()
    db.refresh(document)

    return DocumentResponse.from_document(document)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> None:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    # No ORM relationships/cascades are configured on these models (see
    # db/models.py), and SQLite doesn't enforce foreign keys by default
    # here, so child rows have to be cleaned up explicitly or they'd be
    # orphaned.
    db.query(Summary).filter(Summary.document_id == document_id).delete()
    db.query(Flashcard).filter(Flashcard.document_id == document_id).delete()
    db.query(QuizQuestion).filter(QuizQuestion.document_id == document_id).delete()
    db.query(MindMap).filter(MindMap.document_id == document_id).delete()
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

    storage_service.delete_file(document.stored_filename)

    db.delete(document)
    db.commit()
