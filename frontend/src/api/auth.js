import { API_BASE_URL, apiFetch } from "./config.js";

/**
 * The frontend counterpart to `app/api/v1/routes_auth.py` (V3
 * Milestone 1 Phase 2). Same thin, one-function-per-route convention
 * as api/conversations.js -- no decision logic lives here; see
 * context/AuthContext.jsx for what happens to the Identity these
 * functions resolve to.
 *
 * Every call already goes through apiFetch, so `credentials:
 * "include"` is handled the same way it is for every other request
 * in this app (see api/config.js) -- the authenticated-session cookie
 * these endpoints set is only ever readable by the browser sending it
 * back automatically, never by this code.
 */

/**
 * Turns a failed response's body into a single, human-readable
 * string -- never the raw JS value from `errorBody.detail`.
 *
 * FastAPI's own 422 responses (raised by pydantic field validators in
 * schemas/auth.py -- malformed email, weak password) don't shape
 * `detail` as a string at all: it's an array of structured objects
 * (`[{ loc, msg, type, ... }]`). Manual QA on the first Phase 2 pass
 * found this reaching the UI completely unhandled -- `detail` (an
 * array of objects) got handed straight to `new Error(...)`, whose
 * `.message` became that array's own `String(...)` coercion, i.e.
 * literally the text "[object Object]". This function is what
 * prevents that: a string `detail` (this app's own hand-written
 * HTTPExceptions -- 401, 409) is used as-is; an array `detail`
 * (pydantic's shape) has each entry's `msg` pulled out instead, with
 * pydantic's own "Value error, " prefix stripped (see
 * schemas/auth.py's validators -- they raise plain
 * `ValueError("Please enter a valid email address.")`-style messages;
 * pydantic re-wraps that as "Value error, Please enter a valid email
 * address." in the response, which is the wrapper's own bookkeeping
 * text, not part of the message meant for a person to read).
 */
async function parseErrorDetail(response, fallback) {
  const errorBody = await response.json().catch(() => null);
  const detail = errorBody?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => (typeof item?.msg === "string" ? item.msg.replace(/^Value error,\s*/, "") : null))
      .filter(Boolean);
    if (messages.length > 0) return messages.join(" ");
  }

  return fallback;
}

/**
 * POST /auth/signup. Returns the Identity for the new (and
 * immediately signed-in) account on success. Rejects with an Error
 * whose message is fit to show directly to the person filling out the
 * form -- in particular, a 409 becomes "An account with this email
 * already exists." straight from the backend's own detail message,
 * and a 422 (e.g. too-short password) surfaces the backend's
 * validation message rather than a generic "signup failed".
 */
export async function signup(email, password) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response, `Could not sign up (status ${response.status})`));
  }

  return response.json();
}

/**
 * POST /auth/signin. Returns the authenticated Identity on success.
 * A 401 (wrong password or unknown email -- the backend deliberately
 * doesn't distinguish these, see routes_auth.py) surfaces as a single
 * generic message here too, so the UI never ends up revealing
 * anything the backend intentionally didn't.
 */
export async function signin(email, password) {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response, `Could not sign in (status ${response.status})`));
  }

  return response.json();
}

/**
 * POST /auth/logout. No response body on success (204, see
 * routes_auth.py) -- AuthContext is what decides what the client's
 * identity state becomes afterward (re-resolving it as a guest via
 * getIdentity, rather than this function guessing at a shape for it).
 */
export async function logout() {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/auth/logout`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Could not log out (status ${response.status})`);
  }
}
