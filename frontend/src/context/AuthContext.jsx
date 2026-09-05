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
