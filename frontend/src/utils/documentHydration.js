import { getDocument } from "../api/documents";

/**
 * Resolves a list of persisted document ids into their current
 * records. An id that no longer resolves (the document was deleted,
 * possibly from a different page than the one restoring it) is
 * silently dropped rather than surfacing an error — callers treat a
 * stale id exactly like it was never saved, which is the same
 * fallback behavior the original single-page workspace's restore
 * logic used.
 *
 * Order isn't guaranteed to match `ids` (fetches run in parallel) —
 * callers that care about order should re-sort by the original id
 * list.
 */
export async function hydrateDocumentIds(ids) {
  if (!ids || ids.length === 0) return [];
  const results = await Promise.allSettled(ids.map((id) => getDocument(id)));
  return results
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value);
}
