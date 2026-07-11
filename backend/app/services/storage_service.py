import uuid
from pathlib import Path

# backend/app/services/storage_service.py -> backend/uploads/
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def save_pdf(file_bytes: bytes, original_filename: str) -> str:
    """
    Saves a PDF's raw bytes to disk under a generated filename, never
    the original one. If two people both upload "resume.pdf", using
    their original filenames would let one overwrite the other. Returns
    the generated filename so the caller can store it in the database.
    """
    extension = Path(original_filename).suffix or ".pdf"
    stored_filename = f"{uuid.uuid4()}{extension}"
    (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)
    return stored_filename


def get_path(stored_filename: str) -> Path:
    return UPLOAD_DIR / stored_filename
