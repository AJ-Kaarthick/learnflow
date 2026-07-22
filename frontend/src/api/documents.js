import { API_BASE_URL } from "./config";

/**
 * Uploads a PDF file and returns the created document's metadata
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
 * Returns every previously uploaded document, most recent first. This
 * is what powers the Document Manager list on the home page.
 */
export async function listDocuments() {
  const response = await fetch(`${API_BASE_URL}/api/v1/documents`);

  if (!response.ok) {
    throw new Error(`Could not load documents (status ${response.status})`);
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
