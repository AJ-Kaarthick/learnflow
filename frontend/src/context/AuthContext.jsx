import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { logout as apiLogout, signin as apiSignin, signup as apiSignup } from "../api/auth";
import { getIdentity } from "../api/identity";
import {
  INITIAL_AUTH_STATE,
  authStateAfterAuthError,
  authStateAfterRestoreFailure,
  authStateClearingError,
  authStateFromIdentity,
} from "../utils/authState";

// Centralized authentication state (V3 Milestone 1 Phase 2): this is
// the single place that knows whether the current browser is a guest
// or signed in, and the only thing that calls api/auth.js or
// api/identity.js -- every component (TopBar, AuthPanel, ...) reads
// `identity`/`isAuthenticated` from here rather than each fetching or
// caching its own copy, same "one owner for one piece of cross-app
// state" convention as PersonalizationContext for
// theme/accent/density.
//
// The backend remains the actual source of truth (per this phase's
// brief -- "Backend determines authentication state"): this context
// never invents or assumes an identity, it only reflects whatever
// GET /identity/me, or a signup/signin/logout response, most recently
// said. There is deliberately no localStorage caching of `identity`
// here (unlike some of this project's other state -- see
// utils/persistence.js) -- every page load re-asks the backend via
// the mount effect below, exactly like Phase 1's guest identity
// already relies on the httponly cookie, not the frontend, to
// remember who's who.

const AuthContext = createContext(null);

// V3 Milestone 1 Phase 3: called after signup, signin, and logout all
// succeed, once each has already updated `state` to the new identity.
//
// Introducing real per-identity data (guest/user ownership on
// documents and conversations -- see backend/app/db/models.py) is
// what makes this necessary for the first time: through Phase 1/2,
// every identity saw the exact same global library, so switching
// identity had no visible effect on anything already loaded client-
// side. Now it does -- StudyPage's document list, ChatPage's
// conversation sidebar, and whatever's currently open in the
// workspace were all fetched under the *previous* identity's cookie,
// and have no way to know they need to re-fetch just because
// AuthContext's own state changed underneath them (neither page
// currently takes `identity` as a dependency of its data-loading
// effects).
//
// A full reload is the simplest way to guarantee that every one of
// those, plus anything added later that has the same "loaded under
// whichever identity was active at the time" shape, re-fetches from
// the backend under the browser's new identity -- rather than adding
// an identity-change listener to each page individually today, and to
// every future one that loads identity-scoped data. The tradeoff is
// losing in-memory-only UI state across the reload (e.g. an unsaved
// draft in the chat composer) -- acceptable here because signup,
// signin, and logout are already deliberate, infrequent actions the
// person just took, not something that happens mid-flow.
//
// Guarded for this project's `node --test` frontend suite, which has
// no `window` (see api/config.js's identical guard on
// `import.meta.env` for the same underlying constraint) -- AuthContext
// itself has no test file (this project only unit-tests plain
// functions -- see utils/authState.js -- not components/context, per
// its own established convention), so this only ever actually runs in
// a real browser.
function reloadForIdentitySwitch() {
  if (typeof window !== "undefined" && typeof window.location?.reload === "function") {
    window.location.reload();
  }
}

export function AuthProvider({ children }) {
  const [state, setState] = useState(INITIAL_AUTH_STATE);

  // Restores identity on mount (and therefore on every full page
  // refresh) -- "Restoring current identity on refresh" per the
  // brief. Runs unconditionally, guest or not: GET /identity/me
  // always resolves to *something* (see routes_identity.py), so this
  // is also what establishes the guest session cookie on a
  // completely fresh browser, exactly as it did before this phase
  // existed.
  useEffect(() => {
    let cancelled = false;

    getIdentity()
      .then((identity) => {
        if (!cancelled) setState(authStateFromIdentity(identity));
      })
      .catch((error) => {
        if (!cancelled) setState(authStateAfterRestoreFailure(error));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signup = useCallback(async (email, password) => {
    try {
      const identity = await apiSignup(email, password);
      setState(authStateFromIdentity(identity));
      // V3 Milestone 1 Phase 3: signup is the one action that can
      // bring migrated guest data (documents, conversations) along
      // with it (see routes_auth.py's signup) -- reloading is what
      // actually surfaces that migrated work without asking the
      // person to manually refresh, on top of the general "every
      // identity switch needs a reload" reasoning in
      // reloadForIdentitySwitch's own docstring above.
      reloadForIdentitySwitch();
      return true;
    } catch (error) {
      setState((previous) => authStateAfterAuthError(previous, error));
      return false;
    }
  }, []);

  const signin = useCallback(async (email, password) => {
    try {
      const identity = await apiSignin(email, password);
      setState(authStateFromIdentity(identity));
      reloadForIdentitySwitch();
      return true;
    } catch (error) {
      setState((previous) => authStateAfterAuthError(previous, error));
      return false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
      // The backend has already cleared the authenticated-session
      // cookie (see routes_auth.py:logout) -- re-resolving identity
      // rather than assuming a shape for "logged out" is what picks
      // up whatever guest identity the browser now resolves to,
      // straight from the same source of truth everything else here
      // uses.
      const identity = await getIdentity();
      setState(authStateFromIdentity(identity));
      reloadForIdentitySwitch();
      return true;
    } catch (error) {
      setState((previous) => authStateAfterAuthError(previous, error));
      return false;
    }
  }, []);

  const clearError = useCallback(() => {
    setState((previous) => authStateClearingError(previous));
  }, []);

  const value = useMemo(
    () => ({
      status: state.status,
      identity: state.identity,
      error: state.error,
      isAuthenticated: state.identity?.type === "user",
      isGuest: state.identity?.type === "guest",
      signup,
      signin,
      logout,
      clearError,
    }),
    [state, signup, signin, logout, clearError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
