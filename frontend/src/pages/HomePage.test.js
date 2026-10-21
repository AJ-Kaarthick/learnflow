import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { isRequestCurrent } from "../utils/homeState.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// HomePage Component Contracts (V3 Milestone 6 Phase 1)
// ---------------------------------------------------------------------------

test("1. HomePage.jsx has accessible main container and semantic sections", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /<main[^>]*aria-label="Home Dashboard"/);
  assert.match(source, /<header[^>]*aria-label="Welcome"/);
  assert.match(source, /<section[^>]*aria-label="Workspace Quick Actions"/);
  assert.match(source, /<section[^>]*aria-label="Continue Studying"/);
});

test("2. HomePage.jsx integrates useAuth hook for identity-aware greeting", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{\s*useAuth\s*\}\s*from\s*"\.\.\/context\/AuthContext/);
  assert.match(source, /useAuth\(\)/);
  assert.match(source, /formatGreetingTitle\(identity\)/);
  assert.match(source, /getGreetingSubtitle\(identity\)/);
});

test("3. HomePage.jsx includes guest session callout with AuthPanel trigger", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  // Renders only for unauthenticated guest
  assert.match(source, /!isAuthenticated\s*&&\s*authStatus\s*!==\s*"loading"/);
  assert.match(source, /aria-label="Guest Session Information"/);
  assert.match(source, /Exploring as a guest/);

  // Provides Create Account and Sign In actions
  assert.match(source, /Create Account/);
  assert.match(source, /Sign In/);

  // Integrates AuthPanel component
  assert.match(source, /import\s*AuthPanel\s*from\s*"\.\.\/components\/AuthPanel/);
  assert.match(source, /<AuthPanel[\s\S]*?onClose=\{/);
  assert.match(source, /initialMode=\{authPanelMode\}/);
});

test("4. HomePage.jsx renders 4-way Workspace Quick Actions Grid", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*QUICK_ACTIONS[^}]*\}\s*from\s*"\.\.\/utils\/homeState/);
  assert.match(source, /QUICK_ACTIONS\.map\(/);
  assert.match(source, /routeHref\(action\.route\)/);
  assert.match(source, /action\.title/);
  assert.match(source, /action\.description/);
  assert.match(source, /action\.badge/);
  assert.match(source, /action\.ariaLabel/);
});

test("5. HomePage.jsx preserves Continue Studying recently opened documents", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{\s*listDocuments\s*\}\s*from\s*"\.\.\/api\/documents/);
  assert.match(source, /listDocuments\(\{\s*sort:\s*"recently_opened"\s*\}\)/);
  assert.match(source, /saveActiveDocumentId\(doc\.id\)/);
  assert.match(source, /formatRecentDocumentDate\(doc\.last_opened_at\)/);
  assert.match(source, /View all documents/);
});

// ---------------------------------------------------------------------------
// HomePage Component Contracts (V3 Milestone 6 Phase 2)
// ---------------------------------------------------------------------------

test("6. HomePage.jsx fetches revision sessions and integrates extractInProgressSession", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*listRevisionSessions[^}]*\}\s*from\s*"\.\.\/api\/revision/);
  assert.match(source, /import\s*\{[^}]*extractInProgressSession[^}]*\}\s*from\s*"\.\.\/utils\/homeState/);
  assert.match(source, /listRevisionSessions\(\)/);
  assert.match(source, /extractInProgressSession\(sessions\)/);
});

test("7. HomePage.jsx renders In-Progress Revision card when an active session is present", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /aria-label="In-Progress Revision"/);
  assert.match(source, /data-testid="in-progress-revision-card"/);
  assert.match(source, /inProgressSession\.title/);
  assert.match(source, /formatInProgressSessionProgress\(inProgressSession\)/);
  assert.match(source, /Resume Session/);
});

test("8. HomePage.jsx invokes savePendingRevisionResume on Resume Session click", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*savePendingRevisionResume[^}]*\}\s*from\s*"\.\.\/utils\/revisionState/);
  assert.match(source, /savePendingRevisionResume\(sessionId,\s*identity\)/);
  assert.match(source, /handleResumeSession\(inProgressSession\.id\)/);
  assert.match(source, /routeHref\(ROUTES\.REVISION\)/);
});

test("9. HomePage.jsx isolates requests across identity changes with scoped dependencies", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  // Document list and revision session effects depend on [identity, authStatus]
  assert.match(source, /},\s*\[identity,\s*authStatus\]\);/);
});

// ---------------------------------------------------------------------------
// HomePage Component Contracts (V3 Milestone 6 Phase 3)
// ---------------------------------------------------------------------------

test("10. HomePage.jsx fetches recommendations and weak topics from Progress API", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*getProgressRecommendations[^}]*\}\s*from\s*"\.\.\/api\/progress/);
  assert.match(source, /import\s*\{[^}]*getProgressWeakTopics[^}]*\}\s*from\s*"\.\.\/api\/progress/);
  assert.match(source, /getProgressRecommendations\(\{\s*limit:\s*2/);
  assert.match(source, /getProgressWeakTopics\(\{/);
});

test("11. HomePage.jsx renders Action Center with accessible landmark and recommendation cards", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /aria-label="Action Center"/);
  assert.match(source, /data-testid="recommendation-card"/);
  assert.match(source, /getRecommendationBadge\(rec\.type\)/);
  assert.match(source, /getRecommendationActionText\(rec\)/);
  assert.match(source, /handleLaunchRecommendation\(rec\)/);
  assert.match(source, /View progress analytics/);
});

test("12. HomePage.jsx renders Weak Topics section with truthful empty state and practice CTA", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /aria-label="Weak Topics"/);
  assert.match(source, /data-testid="weak-topic-card"/);
  assert.match(source, /No practice-ready weak topics right now\./);
  assert.match(source, /Review your complete topic history and learning insights in/);
  assert.match(source, /routeHref\(ROUTES\.PROGRESS\)/);
  assert.match(source, /handleLaunchWeakTopic\(wt\)/);
  assert.match(source, /Practice Topic/);
});

test("13. HomePage.jsx invokes savePendingRevisionLaunch on recommendation action click", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*savePendingRevisionLaunch[^}]*\}\s*from\s*"\.\.\/utils\/progressState/);
  assert.match(source, /import\s*\{[^}]*createLaunchPayloadFromRecommendation[^}]*\}\s*from\s*"\.\.\/utils\/progressState/);
  assert.match(source, /createLaunchPayloadFromRecommendation\(rec\)/);
  assert.match(source, /savePendingRevisionLaunch\(payload,\s*identity\)/);
  assert.match(source, /window\.location\.hash\s*=\s*routeHref\(ROUTES\.REVISION\)/);
});

test("14. HomePage.jsx invokes savePendingRevisionLaunch on weak topic practice click", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*createLaunchPayloadFromWeakTopic[^}]*\}\s*from\s*"\.\.\/utils\/progressState/);
  assert.match(source, /createLaunchPayloadFromWeakTopic\(\{/);
  assert.match(source, /topic_display:\s*topic\.topicDisplay/);
  assert.match(source, /savePendingRevisionLaunch\(payload,\s*identity\)/);
});

test("15. HomePage.jsx distinguishes actionable items from archived or unready items", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /const isActionable = rec\.isActionable && !rec\.isArchived;/);
  assert.match(source, /getRecommendationActionText\(rec\)/);
  assert.match(source, /wt\.isArchived\s*\?\s*"Archived"\s*:\s*"Not Ready"/);
});

test("16. HomePage.jsx guards retries and loads against cross-identity and stale-response races", () => {
  const source = readFileSync(join(__dirname, "./HomePage.jsx"), "utf-8");

  assert.match(source, /const\s+currentScope\s*=\s*getIdentityScope\(identity\);/);
  assert.match(source, /recGenRef\s*=\s*useRef\(0\)/);
  assert.match(source, /recAbortRef\s*=\s*useRef\(null\)/);
  assert.match(source, /weakTopicsGenRef\s*=\s*useRef\(0\)/);
  assert.match(source, /weakTopicsAbortRef\s*=\s*useRef\(null\)/);
  assert.match(source, /isRequestCurrent/);

  // Independent retry handlers bump generation and abort prior requests
  assert.match(source, /function\s+retryRecommendations\(\)\s*\{[\s\S]*?recGenRef\.current\s*\+/);
  assert.match(source, /function\s+retryWeakTopics\(\)\s*\{[\s\S]*?weakTopicsGenRef\.current\s*\+/);
});

test("17. Simulation: outstanding retry followed by identity change cannot overwrite new identity state", async () => {
  // Simulate the HomePage async state machine and refs
  let currentScope = "guest:g-1";
  const currentScopeRef = { current: currentScope };
  const recGenRef = { current: 1 };
  const recAbortRef = { current: new AbortController() };

  let displayedRecommendations = [];
  let recommendationsError = null;
  let loadingRecommendations = false;

  // Deferred promise simulating slow network response for Identity 1 retry
  let resolveIdentity1Retry;
  const identity1Promise = new Promise((resolve) => {
    resolveIdentity1Retry = resolve;
  });

  // 1. User on Identity 1 clicks Retry Recommendations
  const retryGen = recGenRef.current + 1;
  recGenRef.current = retryGen;
  const retryScope = currentScope;
  loadingRecommendations = true;
  recommendationsError = null;

  const retryPromise = identity1Promise.then((data) => {
    if (isRequestCurrent(retryGen, retryScope, recGenRef.current, currentScopeRef.current)) {
      displayedRecommendations = data;
    }
  }).catch((err) => {
    if (isRequestCurrent(retryGen, retryScope, recGenRef.current, currentScopeRef.current)) {
      recommendationsError = err?.message;
    }
  }).finally(() => {
    if (isRequestCurrent(retryGen, retryScope, recGenRef.current, currentScopeRef.current)) {
      loadingRecommendations = false;
    }
  });

  // 2. Identity changes to "user:u-2" before Identity 1's retry resolves
  currentScope = "user:u-2";
  currentScopeRef.current = currentScope;
  recAbortRef.current?.abort();
  recGenRef.current += 1; // Invalidate all pending requests for Identity 1
  displayedRecommendations = []; // Cleared on switch
  recommendationsError = null;

  // 3. Identity 1's retry resolves with stale data
  resolveIdentity1Retry([{ id: "stale-rec", title: "Identity 1 Stale Recommendation" }]);
  await retryPromise;

  // Stale result MUST NOT overwrite Identity 2's empty/clean state!
  assert.deepEqual(displayedRecommendations, [], "Stale Identity 1 retry must not overwrite Identity 2 state");
  assert.equal(recommendationsError, null, "Stale Identity 1 error must not be set");
  assert.notEqual(displayedRecommendations[0]?.id, "stale-rec");
});

test("18. Simulation: out-of-order retries on same identity ignore older requests", async () => {
  const currentScope = "user:u-1";
  const currentScopeRef = { current: currentScope };
  const recGenRef = { current: 0 };

  let displayedRecommendations = [];

  let resolveFirstRetry;
  const firstPromise = new Promise((resolve) => {
    resolveFirstRetry = resolve;
  });

  let resolveSecondRetry;
  const secondPromise = new Promise((resolve) => {
    resolveSecondRetry = resolve;
  });

  // First retry launched (Gen 1)
  const gen1 = ++recGenRef.current;
  const p1 = firstPromise.then((data) => {
    if (isRequestCurrent(gen1, currentScope, recGenRef.current, currentScopeRef.current)) {
      displayedRecommendations = data;
    }
  });

  // Second retry launched (Gen 2)
  const gen2 = ++recGenRef.current;
  const p2 = secondPromise.then((data) => {
    if (isRequestCurrent(gen2, currentScope, recGenRef.current, currentScopeRef.current)) {
      displayedRecommendations = data;
    }
  });

  // Second retry resolves first
  resolveSecondRetry([{ id: "fast-fresh", title: "Newer Retry Data" }]);
  await p2;
  assert.equal(displayedRecommendations[0]?.id, "fast-fresh");

  // First retry resolves second (late)
  resolveFirstRetry([{ id: "slow-stale", title: "Older Retry Data" }]);
  await p1;

  // Second retry data remains in place; older retry was ignored
  assert.equal(displayedRecommendations[0]?.id, "fast-fresh");
});
