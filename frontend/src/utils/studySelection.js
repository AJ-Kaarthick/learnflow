import { toDocumentChip } from "./documentChip.js";

/**
 * Maximum number of documents that can be selected for a Study session.
 * Matches the chat adaptive retrieval budget maximum (MAX_DOCUMENT_IDS = 10).
 */
export const MAX_STUDY_DOCUMENTS = 10;

/**
 * Resolves which document should be considered the "active" or focused
 * document for single-document study tools (Summary, Flashcards, Quiz,
 * Mind Map) within a selection.
 *
 * Prefers the document matching `preferredActiveId` if still present in
 * `documents`. If not found, falls back to the first readable document
 * in `documents` (so the student immediately sees working study panels),
 * or simply the first document if none are readable. Returns null if
 * `documents` is empty.
 */
export function resolveActiveStudyDocument(documents, preferredActiveId = null) {
  if (!documents || documents.length === 0) return null;

  if (preferredActiveId != null) {
    const found = documents.find((doc) => doc.id === preferredActiveId);
    if (found) return found;
  }

  const readable = documents.find(
    (doc) => doc.status === "ready" && (doc.character_count ?? 0) > 0
  );
  return readable || documents[0];
}

/**
 * Toggles a document's presence in the current study selection.
 *
 * - If already selected: removes it.
 * - If not selected: appends it up to `maxAllowed`. If the limit is reached,
 *   rejects the addition and returns an informative error message.
 */
export function toggleStudyDocument(
  currentDocuments,
  documentToToggle,
  maxAllowed = MAX_STUDY_DOCUMENTS
) {
  const isSelected = currentDocuments.some((doc) => doc.id === documentToToggle.id);

  if (isSelected) {
    const nextDocuments = currentDocuments.filter((doc) => doc.id !== documentToToggle.id);
    return {
      nextDocuments,
      error: null,
    };
  }

  if (currentDocuments.length >= maxAllowed) {
    return {
      nextDocuments: currentDocuments,
      error: `You can select up to ${maxAllowed} documents for study.`,
    };
  }

  return {
    nextDocuments: [...currentDocuments, toDocumentChip(documentToToggle)],
    error: null,
  };
}

/**
 * Handles clicking a document in the library.
 *
 * - In single-document mode (0 or 1 document selected): replaces the
 *   selection with `[newDocument]` (classic V2.4 behavior).
 * - In multi-document mode (2+ documents selected):
 *   - If `newDocument` is already selected, keeps the selection intact and
 *     focuses it.
 *   - If not selected, appends it up to `maxAllowed`. If at limit, returns an
 *     error.
 */
export function openStudyDocument(
  currentDocuments,
  newDocument,
  maxAllowed = MAX_STUDY_DOCUMENTS
) {
  const chip = toDocumentChip(newDocument);

  if (!currentDocuments || currentDocuments.length <= 1) {
    return {
      nextDocuments: [chip],
      activeDocument: chip,
      error: null,
    };
  }

  const alreadySelected = currentDocuments.some((doc) => doc.id === newDocument.id);
  if (alreadySelected) {
    return {
      nextDocuments: currentDocuments,
      activeDocument: chip,
      error: null,
    };
  }

  if (currentDocuments.length >= maxAllowed) {
    return {
      nextDocuments: currentDocuments,
      activeDocument: currentDocuments[0],
      error: `You can select up to ${maxAllowed} documents for study.`,
    };
  }

  return {
    nextDocuments: [...currentDocuments, chip],
    activeDocument: chip,
    error: null,
  };
}

/**
 * Removes a document from the selection by id.
 */
export function removeStudyDocument(currentDocuments, documentId) {
  const nextDocuments = (currentDocuments ?? []).filter((doc) => doc.id !== documentId);
  return {
    nextDocuments,
  };
}

/**
 * Synchronizes the study selection when a new document upload completes.
 *
 * - In single-document mode (0 or 1 document selected): the uploaded
 *   document becomes the sole selection and active document.
 * - In multi-document mode: appends the new document if under `maxAllowed`.
 */
export function syncStudyUpload(
  currentDocuments,
  newDocument,
  maxAllowed = MAX_STUDY_DOCUMENTS
) {
  const chip = toDocumentChip(newDocument);

  if (!currentDocuments || currentDocuments.length <= 1) {
    return {
      nextDocuments: [chip],
      activeDocument: chip,
    };
  }

  const alreadySelected = currentDocuments.some((doc) => doc.id === newDocument.id);
  if (alreadySelected) {
    return {
      nextDocuments: currentDocuments,
      activeDocument: chip,
    };
  }

  if (currentDocuments.length >= maxAllowed) {
    return {
      nextDocuments: currentDocuments,
      activeDocument: chip,
    };
  }

  return {
    nextDocuments: [...currentDocuments, chip],
    activeDocument: chip,
  };
}
