import { API_BASE_URL } from "./config";

/**
 * Uploads a document (PDF, DOCX, or PPTX) and returns the created document's metadata
 * (id, status, extracted text preview). Throws with the backend's
 * error message if the upload is rejected (wrong file type, too
 * large, etc.) so the UI can show something meaningful.
 */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Upload failed with status ${response.status}`);
  }

  return response.json();
}

export async function getDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`);

  if (!response.ok) {
    throw new Error(`Could not load document (status ${response.status})`);
  }

  return response.json();
}

/**
 * Returns documents for the Document Library, optionally filtered by
 * a case-insensitive partial filename match and/or sorted. `sort`
 * mirrors the backend's DocumentSortOption values exactly
 * ("name_asc", "name_desc", "uploaded_newest", "uploaded_oldest",
 * "recently_opened") — see routes_documents.py.
 */
export async function listDocuments({ search, sort } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (sort) params.set("sort", sort);
  const queryString = params.toString();

  const response = await fetch(`${API_BASE_URL}/api/v1/documents${queryString ? `?${queryString}` : ""}`);

  if (!response.ok) {
    throw new Error(`Could not load documents (status ${response.status})`);
  }

  return response.json();
}

/**
 * Marks a document as opened (sets last_opened_at server-side), which
 * is what powers the "Recently Opened" sort. Call whenever the user
 * opens an existing document from the library.
 */
export async function markDocumentOpened(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/open`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Could not mark document opened (status ${response.status})`);
  }

  return response.json();
}

export async function renameDocument(documentId, newName) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ original_filename: newName }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Rename failed (status ${response.status})`);
  }

  return response.json();
}

export async function deleteDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || `Delete failed (status ${response.status})`);
  }
}
