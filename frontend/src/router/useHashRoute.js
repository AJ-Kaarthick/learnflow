import { useEffect, useState } from "react";

/**
 * V2.4 Milestone 1 introduces LearnFlow's first top-level pages. The
 * long-term nav is Home | Study | Chat | Recall | Revision (plus
 * Settings/Auth later) — this milestone only implements the first
 * three, but routing itself is built to grow into the rest without a
 * rewrite: adding Recall later is one new entry here plus one new
 * page component, not a new routing system.
 *
 * The project has no routing library and doesn't need one yet — three
 * flat, unparameterized pages is exactly the case `window.location.hash`
 * plus a `hashchange` listener already covers, with two things a
 * library would otherwise be pulled in for: real URLs (bookmarkable,
 * shareable, deep-linkable) and native browser back/forward, both for
 * free. If a future milestone needs nested/parameterized routes (e.g.
 * a specific document or conversation in the URL), that's the point
 * to reach for a real router — not before.
 */

export const ROUTES = {
  HOME: "home",
  STUDY: "study",
  CHAT: "chat",
};

const VALID_ROUTES = new Set(Object.values(ROUTES));
const DEFAULT_ROUTE = ROUTES.HOME;

// Only the first path segment matters for now (no nested routes) —
// anything unrecognized (including an empty/missing hash on first
// visit) falls back to Home, so a stale or hand-edited URL never
// leaves the app on a blank page.
function parseRoute(hash) {
  const segment = hash.replace(/^#\/?/, "").split(/[/?]/)[0];
  return VALID_ROUTES.has(segment) ? segment : DEFAULT_ROUTE;
}

export function routeHref(route) {
  return `#/${route}`;
}

// Tracks the current route from the URL hash. Navigation itself is
// just a normal <a href={routeHref(...)}> (see AppNav, HomePage) — no
// imperative navigate() function is needed anywhere in this
// milestone, even for links that also set some other piece of state
// as a side effect (e.g. Home's "continue studying" cards, which set
// the active document in an onClick alongside their real `href` to
// Study) — the href does the actual navigating, onClick just does the
// extra bit of bookkeeping alongside it.
export function useHashRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));

  useEffect(() => {
    function handleHashChange() {
      setRoute(parseRoute(window.location.hash));
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return route;
}
