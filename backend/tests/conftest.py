"""
Test-session isolation for the backend test suite.

Without this, the test suite uses the exact same on-disk SQLite
database and uploads directory a developer's local server would use
(see `database_url`'s default in app/core/config.py and
app/services/storage_service.py's UPLOAD_DIR) — both plain file paths,
neither reset between runs. A single `pytest` invocation is internally
consistent (every test here uses distinct ids/filenames), but running
the suite twice in a row reuses whatever the previous run left behind.
That's what turns test_document_manager.py's fixed-filename rename
tests into flaky 409 Conflicts on a second run: not a bug in the app
or in those tests, just a missing fixture — the suite was never told
to isolate itself.

Fix: point the database and uploads directory at a fresh temporary
location for the whole test session, and remove both when the session
ends. This has to happen before app.db.database (and therefore
app.main) is imported anywhere, which is exactly what a conftest.py
guarantees — pytest imports it before collecting any test module in
this directory.

No production code changes needed: `database_url` is already read
from the environment (see Settings in app/core/config.py — this is
what DATABASE_URL/.env are for), and storage_service.UPLOAD_DIR is a
plain module attribute, so tests are free to point it elsewhere for
the duration of the run without storage_service.py itself changing at
all.
"""

import os
import shutil
import tempfile
from pathlib import Path

# Must happen before any `app.*` import (including ones below) —
# Settings() reads DATABASE_URL from the environment once, at import
# time, so this has to be set first.
_db_fd, _TEST_DB_PATH = tempfile.mkstemp(prefix="learnflow-test-", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="learnflow-test-uploads-")

from app.services import storage_service  # noqa: E402  (see comment above)

storage_service.UPLOAD_DIR = Path(_TEST_UPLOAD_DIR)


def pytest_sessionfinish(session, exitstatus):
    """Removes the temporary database file and uploads directory this session created."""
    Path(_TEST_DB_PATH).unlink(missing_ok=True)
    shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True)
