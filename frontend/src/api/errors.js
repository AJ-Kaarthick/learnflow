/**
 * Turns a failed fetch Response into a single Error every api/*.js
 * module and every component can treat the same way — one place that
 * knows about every shape a backend `detail` can take, instead of
 * each api module reinventing (or half-reinventing) this itself.
 *
 * Before V3 Milestone 1 Phase 3, most api modules (documents.js,
 * chat.js, flashcards.js, quiz.js, mindmap.js, summary.js,
 * conversations.js) used a one-line version of this —
 * `errorBody?.detail || fallback` — that only ever worked when
 * `detail` was already a string. Two shapes it didn't handle:
 *
 * - FastAPI/pydantic's own 422 validation errors, where `detail` is
 *   an array of `{ loc, msg, type, ... }` objects, not a string.
 *   api/auth.js grew its own fix for exactly this on the first Phase
 *   2 pass (see git history / that file's old parseErrorDetail) after
 *   manual QA found it rendering as the literal text "[object
 *   Object]" — `new Error(detail)` on a non-string `detail` sets
 *   `.message` to `String(detail)`, and `String([{...}])` (or
 *   `String({...})`) is exactly that string.
 * - This phase's own new guest-limit shape (see
 *   guest_limit_service.to_http_exception in the backend) — `detail`
 *   is an object like `{ code: "guest_limit_reached", limit_type,
 *   limit, used, message }`. Every api module that can now hit a
 *   guest limit (documents.js's upload, chat.js's two endpoints,
 *   conversations.js's sendConversationMessage, and
 *   summary/flashcards/quiz/mindmap.js's generation calls) needs the
 *   exact same "[object Object]" bug fixed for this new shape too,
 *   which is the actual reason this stopped being worth copy-pasting
 *   per file and became its own module.
 *
 * Consolidating both fixes here means every api module gets both for
 * free, and a third shape showing up in the future only needs
 * handling once.
 */

/**
 * Thrown instead of a plain Error when a backend response is
 * specifically a guest-usage-limit rejection (403,
 * `detail.code === "guest_limit_reached"`). Callers that don't care
 * about the distinction can still just read `.message`, exactly like
 * any other Error — components that want to additionally offer a
 * "sign up to continue" affordance (see components/GuestLimitNotice.jsx)
 * check `error.code === "guest_limit_reached"` (or `instanceof
 * GuestLimitError`) to decide whether to show it.
 */
export class GuestLimitError extends Error {
  constructor(message, { limitType, limit, used } = {}) {
    super(message);
    this.name = "GuestLimitError";
    this.code = "guest_limit_reached";
    this.limitType = limitType;
    this.limit = limit;
    this.used = used;
  }
}

/**
 * True for any error this module produced for a guest-limit
 * rejection — a plain property check rather than always requiring
 * `instanceof GuestLimitError`, since the two are equivalent here but
 * a property check reads more naturally at a call site that already
 * has other `error.something` checks nearby.
 */
export function isGuestLimitError(error) {
  return Boolean(error) && error.code === "guest_limit_reached";
}

/**
 * Reads and parses a failed Response's JSON body into a single Error,
 * choosing the right shape-specific handling for whatever `detail`
 * turned out to be. Always resolves to an Error (or subclass) with a
 * plain, human-readable `.message` — never rejects, and never lets a
 * non-string value reach `new Error(...)` directly.
 */
export async function parseErrorResponse(response, fallback) {
  const errorBody = await response.json().catch(() => null);
  const detail = errorBody?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return new Error(detail);
  }

  if (Array.isArray(detail) && detail.length > 0) {
    // FastAPI/pydantic's 422 shape: each entry's `msg` carries the
    // actual message, prefixed with pydantic's own "Value error, "
    // bookkeeping text for a validator's plain ValueError (see e.g.
    // schemas/auth.py's password/email validators) -- stripped here
    // since it's an implementation detail of *how* the message was
    // raised, not part of the message itself.
    const messages = detail
      .map((item) => (typeof item?.msg === "string" ? item.msg.replace(/^Value error,\s*/, "") : null))
      .filter(Boolean);
    if (messages.length > 0) return new Error(messages.join(" "));
  }

  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    if (detail.code === "guest_limit_reached" && typeof detail.message === "string") {
      return new GuestLimitError(detail.message, {
        limitType: detail.limit_type,
        limit: detail.limit,
        used: detail.used,
      });
    }

    // An object shape this function doesn't specifically recognize --
    // rather than handing it to `new Error(...)` and risking another
    // "[object Object]", fall back to a human `.message` field if the
    // backend happened to include one, otherwise the generic fallback.
    return new Error(typeof detail.message === "string" && detail.message ? detail.message : fallback);
  }

  return new Error(fallback);
}
