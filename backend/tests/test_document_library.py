import io
import uuid

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app

client = TestClient(app)


def _make_test_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(100, 750, text)
    pdf.save()
    return buffer.getvalue()


def _upload(filename: str) -> str:
    pdf_bytes = _make_test_pdf("Some content.")
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    return response.json()["id"]


def _unique_tag() -> str:
    # Every search/sort test scopes itself to documents tagged with a
    # one-off unique string, since the test DB is shared across the
    # whole test run (no per-test isolation) and will already contain
    # documents from other tests.
    return uuid.uuid4().hex[:8]


# --- Search -----------------------------------------------------------------


def test_search_matches_partial_filename():
    tag = _unique_tag()
    _upload(f"{tag}-Biology Notes.pdf")
    _upload(f"{tag}-Chemistry Notes.pdf")
    _upload(f"{tag}-History Essay.pdf")

    response = client.get("/api/v1/documents", params={"search": f"{tag}-Bio"})

    assert response.status_code == 200
    names = [doc["original_filename"] for doc in response.json()]
    assert names == [f"{tag}-Biology Notes.pdf"]


def test_search_is_case_insensitive():
    tag = _unique_tag()
    _upload(f"{tag}-Workout Plan.pdf")

    response = client.get("/api/v1/documents", params={"search": f"{tag}-WORKOUT"})

    assert response.status_code == 200
    names = [doc["original_filename"] for doc in response.json()]
    assert names == [f"{tag}-Workout Plan.pdf"]


def test_search_matches_anywhere_in_filename_not_just_prefix():
    tag = _unique_tag()
    _upload(f"{tag}-Final Report.pdf")

    response = client.get("/api/v1/documents", params={"search": "Report"})

    assert response.status_code == 200
    names = [doc["original_filename"] for doc in response.json()]
    assert f"{tag}-Final Report.pdf" in names


def test_search_with_no_matches_returns_empty_list_for_that_filter():
    tag = _unique_tag()
    _upload(f"{tag}-Notes.pdf")

    response = client.get("/api/v1/documents", params={"search": f"{tag}-doesnotexist"})

    assert response.status_code == 200
    assert response.json() == []


def test_blank_search_behaves_like_no_search():
    tag = _unique_tag()
    doc_id = _upload(f"{tag}-Doc.pdf")

    response = client.get("/api/v1/documents", params={"search": "   "})

    assert response.status_code == 200
    ids = [doc["id"] for doc in response.json()]
    assert doc_id in ids


def test_search_escapes_like_wildcards():
    tag = _unique_tag()
    _upload(f"{tag}-100% Done.pdf")
    _upload(f"{tag}-anything.pdf")

    # A literal "%" in the search shouldn't act as a wildcard matching
    # every document.
    response = client.get("/api/v1/documents", params={"search": f"{tag}-100%"})

    assert response.status_code == 200
    names = [doc["original_filename"] for doc in response.json()]
    assert names == [f"{tag}-100% Done.pdf"]


# --- Sorting ------------------------------------------------------------


def test_sort_name_asc_and_desc():
    tag = _unique_tag()
    a_id = _upload(f"{tag}-Apple.pdf")
    b_id = _upload(f"{tag}-banana.pdf")  # lowercase on purpose
    c_id = _upload(f"{tag}-Cherry.pdf")

    asc = client.get("/api/v1/documents", params={"search": tag, "sort": "name_asc"})
    ids_asc = [doc["id"] for doc in asc.json()]
    assert ids_asc == [a_id, b_id, c_id]

    desc = client.get("/api/v1/documents", params={"search": tag, "sort": "name_desc"})
    ids_desc = [doc["id"] for doc in desc.json()]
    assert ids_desc == [c_id, b_id, a_id]


def test_sort_uploaded_newest_and_oldest():
    tag = _unique_tag()
    first_id = _upload(f"{tag}-first.pdf")
    second_id = _upload(f"{tag}-second.pdf")

    newest = client.get("/api/v1/documents", params={"search": tag, "sort": "uploaded_newest"})
    assert [doc["id"] for doc in newest.json()] == [second_id, first_id]

    oldest = client.get("/api/v1/documents", params={"search": tag, "sort": "uploaded_oldest"})
    assert [doc["id"] for doc in oldest.json()] == [first_id, second_id]


def test_sort_defaults_to_uploaded_newest_when_omitted():
    tag = _unique_tag()
    first_id = _upload(f"{tag}-first.pdf")
    second_id = _upload(f"{tag}-second.pdf")

    response = client.get("/api/v1/documents", params={"search": tag})

    assert [doc["id"] for doc in response.json()] == [second_id, first_id]


def test_sort_rejects_invalid_value():
    response = client.get("/api/v1/documents", params={"sort": "not_a_real_option"})

    assert response.status_code == 422


def test_sort_recently_opened_reflects_open_order():
    tag = _unique_tag()
    a_id = _upload(f"{tag}-A.pdf")
    b_id = _upload(f"{tag}-B.pdf")

    # Neither opened yet: falls back to upload recency (B before A).
    response = client.get("/api/v1/documents", params={"search": tag, "sort": "recently_opened"})
    assert [doc["id"] for doc in response.json()] == [b_id, a_id]

    # Opening A brings it to the front.
    open_response = client.post(f"/api/v1/documents/{a_id}/open")
    assert open_response.status_code == 200
    assert open_response.json()["last_opened_at"] is not None

    response = client.get("/api/v1/documents", params={"search": tag, "sort": "recently_opened"})
    assert [doc["id"] for doc in response.json()] == [a_id, b_id]

    # Opening B afterwards brings it back to the front.
    client.post(f"/api/v1/documents/{b_id}/open")

    response = client.get("/api/v1/documents", params={"search": tag, "sort": "recently_opened"})
    assert [doc["id"] for doc in response.json()] == [b_id, a_id]


# --- Open tracking --------------------------------------------------------


def test_open_document_sets_last_opened_at():
    doc_id = _upload("open-me.pdf")

    get_before = client.get(f"/api/v1/documents/{doc_id}")
    assert get_before.json()["last_opened_at"] is None

    response = client.post(f"/api/v1/documents/{doc_id}/open")

    assert response.status_code == 200
    assert response.json()["last_opened_at"] is not None
    assert response.json()["id"] == doc_id


def test_open_document_404_for_missing_document():
    response = client.post("/api/v1/documents/does-not-exist/open")

    assert response.status_code == 404
