import { API_BASE_URL, apiFetch } from "./config.js";

/**
 * The frontend counterpart to `app/api/v1/routes_identity.py`'s
 * GET /identity/me. Kept as its own module (mirroring the backend's
 * own routes_identity.py vs. routes_auth.py split) rather than folded
 * into api/auth.js, since this one endpoint answers a different
 * question -- "who am I right now?" -- than the three signup/signin/
 * logout actions in auth.js.
 *
 * V3 Milestone 1 Phase 2 widened what this returns (an `email` field,
 * present for an authenticated user and `null` for a guest -- see
 * schemas/identity.py's Identity), but this function's own contract
 * (a single thin GET) is unchanged from what Phase 1 already had
 * running server-side; Phase 1 just had no frontend caller for it
 * yet.
 */
export async function getIdentity() {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/identity/me`);

  if (!response.ok) {
    throw new Error(`Could not resolve the current identity (status ${response.status})`);
  }

  return response.json();
}
