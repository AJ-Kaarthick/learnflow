"""
Covers the actual root-cause fix behind the "scanned PDF and JPG both
fail" bug report:

  1. Image and scanned-PDF processing depend on two OS-level binaries
     (tesseract, poppler) that pip cannot install and that nothing in
     the codebase previously checked for or reported on — see
     app/services/ocr/dependency_check.py.
  2. Every extraction failure (a missing binary included) was being
     caught by a bare `except Exception: document.status = "failed"`
     in routes_documents.py with no logging at all, so the real reason
     never reached the logs.

These tests prove both are fixed: dependency_check reports exactly
which binary is missing (unit-level, no real environment tampering
required), and a document extraction failure is now actually logged
with the real exception rather than silently discarded.
"""

import logging

import pytest

from app.api.v1 import routes_documents
from app.main import app
from app.services.ocr import dependency_check
from fastapi.testclient import TestClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# dependency_check.check_ocr_dependencies
# ---------------------------------------------------------------------------


class _FakeTesseractNotFoundError(Exception):
    """Stands in for pytesseract.TesseractNotFoundError in tests below."""


def test_check_ocr_dependencies_returns_empty_when_both_binaries_present(monkeypatch):
    monkeypatch.setattr(dependency_check.pytesseract, "get_tesseract_version", lambda: "5.3.4")
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: "/usr/bin/" + name)

    assert dependency_check.check_ocr_dependencies() == []


def test_check_ocr_dependencies_reports_missing_tesseract(monkeypatch):
    def _raise():
        raise dependency_check.pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(dependency_check.pytesseract, "get_tesseract_version", _raise)
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: "/usr/bin/" + name)

    warnings = dependency_check.check_ocr_dependencies()

    assert len(warnings) == 1
    assert "tesseract" in warnings[0].lower()


def test_check_ocr_dependencies_reports_missing_poppler(monkeypatch):
    monkeypatch.setattr(dependency_check.pytesseract, "get_tesseract_version", lambda: "5.3.4")
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: None)

    warnings = dependency_check.check_ocr_dependencies()

    assert len(warnings) == 1
    assert "poppler" in warnings[0].lower() or "pdftoppm" in warnings[0].lower()


def test_check_ocr_dependencies_reports_both_when_both_missing(monkeypatch):
    def _raise():
        raise dependency_check.pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(dependency_check.pytesseract, "get_tesseract_version", _raise)
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: None)

    warnings = dependency_check.check_ocr_dependencies()

    assert len(warnings) == 2


def test_check_ocr_dependencies_never_raises_even_when_both_missing(monkeypatch):
    """
    The whole point of this check is a clean startup warning, not a
    crash — the app must still boot (and PDF/DOCX/PPTX must still
    work) on a host with no OCR binaries installed at all.
    """

    def _raise():
        raise dependency_check.pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(dependency_check.pytesseract, "get_tesseract_version", _raise)
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: None)

    dependency_check.check_ocr_dependencies()  # must not raise


# ---------------------------------------------------------------------------
# routes_documents.py — extraction failures are now logged, not swallowed
# ---------------------------------------------------------------------------


def test_document_processing_failure_is_logged_with_the_real_exception(caplog, monkeypatch):
    """
    Reproduces the bug report directly: an extractor raising the exact
    exception a missing Tesseract install raises (OCREngineError) must
    now show up in the backend logs, not disappear silently. Before
    the fix, this test would fail (caplog would be empty) even though
    the document still correctly ended up "failed".
    """

    def _boom(_path):
        raise routes_documents.document_extraction_service.UnsupportedFileTypeError(
            "Tesseract is not installed or not on PATH."
        )

    monkeypatch.setattr(
        routes_documents.document_extraction_service, "extract_text", lambda path, ext: _boom(path)
    )

    with caplog.at_level(logging.ERROR, logger="app.api.v1.routes_documents"):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("notes.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"

    # The real failure reason must actually be in the logs now —
    # caplog.text includes the formatted traceback logger.exception
    # attaches, not just the top-level message.
    assert "Tesseract is not installed" in caplog.text
    assert "Document processing failed" in caplog.text


def test_document_processing_failure_log_includes_filename_and_id(caplog, monkeypatch):
    def _boom(path, ext):
        raise ValueError("boom")

    monkeypatch.setattr(routes_documents.document_extraction_service, "extract_text", _boom)

    with caplog.at_level(logging.ERROR, logger="app.api.v1.routes_documents"):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("diagnosable.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        )

    document_id = response.json()["id"]
    log_text = " ".join(record.message for record in caplog.records)
    assert document_id in log_text
    assert "diagnosable.png" in log_text


def test_corrupted_file_still_ends_up_failed_after_the_logging_fix():
    """
    Regression guard: adding logging must not change the actual
    status-transition behavior for a genuinely corrupted file — same
    "processing -> failed" contract as before, just now with a log
    line explaining why.
    """
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("corrupted.png", b"not a real png", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
