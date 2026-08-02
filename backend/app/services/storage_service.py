import uuid
from pathlib import Path

# backend/app/services/storage_service.py -> backend/uploads/
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def save_uploaded_file(file_bytes: bytes, extension: str) -> str:
    """
    Saves an uploaded file's raw bytes to disk under a generated
    filename, never the original one. If two people both upload
    "resume.pdf", using their original filenames would let one
    overwrite the other. Returns the generated filename so the caller
    can store it in the database.

    `extension` is passed in explicitly (rather than derived from the
    original filename) so the file on disk always matches the type the
    upload route already validated (see ALLOWED_UPLOAD_TYPES in
    routes_documents.py) — not whatever a possibly-extensionless or
    misleadingly-named original filename happens to end in. Works for
    any file type the upload route accepts (PDF, DOCX, ...); nothing
    here is PDF-specific.
    """
    stored_filename = f"{uuid.uuid4()}{extension}"
    (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)
    return stored_filename


def get_path(stored_filename: str) -> Path:
    return UPLOAD_DIR / stored_filename


def delete_file(stored_filename: str) -> None:
    """
    Removes a stored file from disk. missing_ok=True means deleting an
    already-missing file (e.g. a retry, or manual cleanup) is a no-op
    rather than an error.
    """
    get_path(stored_filename).unlink(missing_ok=True)
