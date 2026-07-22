from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document, Flashcard, MindMap, QuizQuestion, Summary
from app.schemas.document import DocumentRenameRequest, DocumentResponse
from app.services import pdf_service, storage_service
from app.utils import filenames

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPE = "application/pdf"
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    """
    The document history behind the Document Manager. Most recent
    upload first — no pagination yet, fine at the scale a single
    student's document list will realistically reach.
    """
    documents = db.query(Document).order_by(Document.created_at.desc()).all()
    return [DocumentResponse.from_document(document) for document in documents]


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> DocumentResponse:
    if file.content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 20 MB limit.")

    stored_filename = storage_service.save_pdf(file_bytes, original_filename=file.filename)

    # Save a record immediately, before extraction runs, so that even
    # if extraction fails we still know the upload happened and can
    # show a "failed" status instead of losing the record entirely.
    document = Document(
        original_filename=file.filename,
        stored_filename=stored_filename,
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        text = pdf_service.extract_text(storage_service.get_path(stored_filename))
        document.extracted_text = text
        document.status = "ready"
    except Exception:
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

    document.original_filename = f"{base_name}{extension}"
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

    storage_service.delete_pdf(document.stored_filename)

    db.delete(document)
    db.commit()
