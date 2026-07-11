from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Document
from app.schemas.document import DocumentResponse
from app.services import pdf_service, storage_service

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPE = "application/pdf"
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


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
