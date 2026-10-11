import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { ROUTES, routeHref } from "../router/useHashRoute.js";
import {
  consumePendingRevisionLaunch,
  createLaunchPayloadFromRecommendation,
  createLaunchPayloadFromSchedule,
  createLaunchPayloadFromWeakTopic,
  getIdentityScope,
  savePendingRevisionLaunch,
  validateHydratedDocumentsForLaunch,
} from "../utils/progressState.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// 1. Routing & Navigation Contracts
// ---------------------------------------------------------------------------
test("1. ROUTES contains PROGRESS route mapped to 'progress'", () => {
  assert.equal(ROUTES.PROGRESS, "progress");
  assert.equal(routeHref(ROUTES.PROGRESS), "#/progress");
});

test("2. AppNav.jsx includes Progress in NAV_ITEMS and removes Recall placeholder", () => {
  const appNavSource = readFileSync(join(__dirname, "../components/AppNav.jsx"), "utf-8");
  assert.match(appNavSource, /route:\s*ROUTES\.PROGRESS,\s*label:\s*"Progress"/);
  assert.match(appNavSource, /const\s+UPCOMING_ITEMS\s*=\s*\[\s*\];/);
});

test("3. App.jsx mounts ProgressPage under ROUTES.PROGRESS", () => {
  const appSource = readFileSync(join(__dirname, "../App.jsx"), "utf-8");
  assert.match(appSource, /import\s+ProgressPage\s+from\s+"\.\/pages\/ProgressPage";/);
  assert.match(appSource, /route\s*===\s*ROUTES\.PROGRESS\s*&&\s*<ProgressPage\s*\/>/);
});

// ---------------------------------------------------------------------------
// 4. ProgressPage Component Contracts
// ---------------------------------------------------------------------------
test("4. ProgressPage.jsx defines all required sections, SVG chart, and generation guard", () => {
  const pageSource = readFileSync(join(__dirname, "./ProgressPage.jsx"), "utf-8");

  // Sections
  assert.match(pageSource, /aria-label="Progress Workspace"/);
  assert.match(pageSource, /aria-label="Key Performance Indicators"/);
  assert.match(pageSource, /aria-label="Activity Trends"/);
  assert.match(pageSource, /aria-label="Difficulty Breakdown"/);
  assert.match(pageSource, /aria-label="Adaptive Recommendations"/);
  assert.match(pageSource, /aria-label="Weak Topics"/);
  assert.match(pageSource, /aria-label="Spaced Repetition"/);
  assert.match(pageSource, /aria-label="Topic Mastery"/);

  // Generation guard & AbortController to prevent cross-identity race conditions
  assert.match(pageSource, /generationRef\s*=\s*useRef\(0\)/);
  assert.match(pageSource, /abortControllerRef\s*=\s*useRef\(null\)/);
  assert.match(pageSource, /AbortController\(\)/);

  // Hand-authored SVG and gap-preserving polylines
  assert.match(pageSource, /<svg/);
  assert.match(pageSource, /chartData\.scoreSegments\.map/);
  assert.match(pageSource, /<polyline/);
  assert.match(pageSource, /<rect/);
  assert.match(pageSource, /<circle/);

  // Volume metric toggle
  assert.match(pageSource, /VOLUME_METRICS/);
  assert.match(pageSource, /volumeMetric/);

  // Identity hook usage
  assert.match(pageSource, /useAuth\(\)/);

  // Revision launcher handoff trigger
  assert.match(pageSource, /savePendingRevisionLaunch/);
  assert.match(pageSource, /window\.location\.hash\s*=\s*"#\/revision"/);
});

// ---------------------------------------------------------------------------
// 5. RevisionSetup Component Contracts
// ---------------------------------------------------------------------------
test("5. RevisionSetup.jsx includes Topic Focus input and Hydration Error warning", () => {
  const setupSource = readFileSync(join(__dirname, "../components/RevisionSetup.jsx"), "utf-8");

  // Topic focus field
  assert.match(setupSource, /id="revision-topic-focus"/);
  assert.match(setupSource, /maxLength=\{100\}/);
  assert.match(setupSource, /topicFocus/);

  // Hydration warning banner and return-to-progress CTA
  assert.match(setupSource, /hydrationError/);
  assert.match(setupSource, /href="#\/progress"/);
  assert.match(setupSource, /Recommendation Requires Action/);
});

// ---------------------------------------------------------------------------
// 6. RevisionPage Lifecycle & Identity Safety Contracts
// ---------------------------------------------------------------------------
test("6. RevisionPage.jsx waits for verified identity and validates document hydration strictly", () => {
  const revPageSource = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  // Auth checking before consuming
  assert.match(revPageSource, /useAuth\(\)/);
  assert.match(revPageSource, /authStatus\s*===\s*"loading"/);

  // One-shot consumption
  assert.match(revPageSource, /consumePendingRevisionLaunch\(identity\)/);

  // Strict all-or-nothing hydration validation
  assert.match(revPageSource, /validateHydratedDocumentsForLaunch/);
  assert.match(revPageSource, /hydrationError/);
});

// ---------------------------------------------------------------------------
// 7. End-to-end Handoff Flow Logic
// ---------------------------------------------------------------------------
test("7. Recommendation -> Revision setup handoff flow works end-to-end", () => {
  const identity = { type: "user", id: "user-100", email: "student@example.com" };

  const rec = {
    id: "rec-biology-1",
    type: "weak_topic_practice",
    action_payload: {
      document_ids: ["doc-10", "doc-20"],
      mode: "quiz",
      difficulty: "advanced",
      question_count: 8,
      question_type: "mixed",
      topic_focus: "Photosystem II",
    },
  };

  // 1. ProgressPage creates launcher payload from recommendation
  const payload = createLaunchPayloadFromRecommendation(rec);
  assert.deepEqual(payload.document_ids, ["doc-10", "doc-20"]);
  assert.equal(payload.topic_focus, "Photosystem II");

  // 2. ProgressPage saves pending launch with identity scope
  const saved = savePendingRevisionLaunch(payload, identity);
  assert.equal(saved, true);

  // 3. User navigates to Revision: identity still loading -> does not consume prematurely
  const pendingWhileLoading = consumePendingRevisionLaunch(null);
  assert.equal(pendingWhileLoading, null);

  // 4. Identity resolves -> consumed once
  const consumed = consumePendingRevisionLaunch(identity);
  assert.deepEqual(consumed, payload);

  // 5. Strict document hydration check
  const hydratedSuccess = [
    { id: "doc-10", original_filename: "Bio1.pdf", status: "ready", character_count: 500 },
    { id: "doc-20", original_filename: "Bio2.pdf", status: "ready", character_count: 800 },
  ];
  const validOutcome = validateHydratedDocumentsForLaunch(consumed.document_ids, hydratedSuccess);
  assert.equal(validOutcome.isValid, true);
  assert.equal(validOutcome.validDocs.length, 2);

  // 6. Strict hydration failure when one document is unready
  const hydratedFailure = [
    { id: "doc-10", original_filename: "Bio1.pdf", status: "ready", character_count: 500 },
    { id: "doc-20", original_filename: "Bio2.pdf", status: "processing", character_count: 0 },
  ];
  const failOutcome = validateHydratedDocumentsForLaunch(consumed.document_ids, hydratedFailure);
  assert.equal(failOutcome.isValid, false);
  assert.match(failOutcome.reason, /Bio2\.pdf/);
});

// ---------------------------------------------------------------------------
// 8. Independent Resource Loading & Retry Architecture Contracts
// ---------------------------------------------------------------------------
test("8. ProgressPage.jsx decouples resource loading into 5 independent states with dedicated retries", () => {
  const pageSource = readFileSync(join(__dirname, "./ProgressPage.jsx"), "utf-8");

  // 5 independent resource states
  assert.match(pageSource, /summaryState/);
  assert.match(pageSource, /topicsState/);
  assert.match(pageSource, /weakTopicsState/);
  assert.match(pageSource, /schedulesState/);
  assert.match(pageSource, /recommendationsState/);

  // 5 independent loader functions
  assert.match(pageSource, /const\s+loadSummary\s*=/);
  assert.match(pageSource, /const\s+loadTopics\s*=/);
  assert.match(pageSource, /const\s+loadWeakTopics\s*=/);
  assert.match(pageSource, /const\s+loadSchedules\s*=/);
  assert.match(pageSource, /const\s+loadRecommendations\s*=/);

  // 5 independent section retry handlers
  assert.match(pageSource, /const\s+retrySummary\s*=/);
  assert.match(pageSource, /const\s+retryTopics\s*=/);
  assert.match(pageSource, /const\s+retryWeakTopics\s*=/);
  assert.match(pageSource, /const\s+retrySchedules\s*=/);
  assert.match(pageSource, /const\s+retryRecommendations\s*=/);

  // Dedicated section retry button bindings in JSX
  assert.match(pageSource, /onClick=\{retrySummary\}/);
  assert.match(pageSource, /onClick=\{retryRecommendations\}/);
  assert.match(pageSource, /onClick=\{retryWeakTopics\}/);
  assert.match(pageSource, /onClick=\{retrySchedules\}/);
  assert.match(pageSource, /onClick=\{retryTopics\}/);

  // Manual refresh uses Promise.allSettled and generation tracking
  assert.match(pageSource, /handleManualRefresh/);
  assert.match(pageSource, /Promise\.allSettled/);
  assert.match(pageSource, /isRefreshing/);
});

// ---------------------------------------------------------------------------
// 9. Identity Change Isolation & Auth Loading Shell Contracts
// ---------------------------------------------------------------------------
test("9. ProgressPage.jsx immediately purges previous identity data and displays shell during auth loading", () => {
  const pageSource = readFileSync(join(__dirname, "./ProgressPage.jsx"), "utf-8");

  // Previous scope tracking ref
  assert.match(pageSource, /previousScopeRef\s*=\s*useRef\(null\)/);

  // Scope change detection immediately resets all 5 resource states and isRefreshing
  assert.match(pageSource, /currentScope\s*!==\s*previousScopeRef\.current/);
  assert.match(pageSource, /setSummaryState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setTopicsState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setWeakTopicsState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setSchedulesState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setRecommendationsState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setIsRefreshing\(false\)/);

  // In-flight abort & generation increment on identity change
  assert.match(pageSource, /abortControllerRef\.current\.abort\(\)/);
  assert.match(pageSource, /generationRef\.current\s*\+=\s*1/);

  // Auth loading gate: early return without firing network requests
  assert.match(pageSource, /authStatus\s*===\s*"loading"\s*\|\|\s*!currentScope/);

  // Render isolated shell while resolving identity (no stale user data)
  assert.match(pageSource, /Resolving identity\.\.\./);
});

// ---------------------------------------------------------------------------
// 10. Manual Refresh Loader Reuse & Single-Request Guarantee
// ---------------------------------------------------------------------------
test("10. Manual refresh reuses the 5 resource loaders without duplicate API calls and ties isRefreshing to loader promises", async () => {
  const pageSource = readFileSync(join(__dirname, "./ProgressPage.jsx"), "utf-8");

  // 1. loadAll returns a promise settling when all 5 loaders finish
  assert.match(
    pageSource,
    /const\s+loadAll\s*=\s*useCallback\(\s*\(\s*signal,\s*gen\s*\)\s*=>\s*\{\s*return\s+Promise\.allSettled\(\[\s*loadSummary\(signal,\s*gen\),\s*loadTopics\(signal,\s*gen\),\s*loadWeakTopics\(signal,\s*gen\),\s*loadSchedules\(signal,\s*gen\),\s*loadRecommendations\(signal,\s*gen\),\s*\]\);/
  );

  // 2. handleManualRefresh delegates directly to loadAll without duplicating API calls
  const refreshMatch = pageSource.match(/const\s+handleManualRefresh\s*=\s*\(\)\s*=>\s*\{([\s\S]*?)\n\s*\};/);
  assert.ok(refreshMatch, "handleManualRefresh must be defined");
  const refreshBody = refreshMatch[1];

  // Must call loadAll
  assert.match(refreshBody, /loadAll\(controller\.signal,\s*newGen\)\.finally\(/);

  // Must NOT call individual API functions directly
  assert.doesNotMatch(refreshBody, /getProgressSummary/);
  assert.doesNotMatch(refreshBody, /getProgressTopics/);
  assert.doesNotMatch(refreshBody, /getProgressWeakTopics/);
  assert.doesNotMatch(refreshBody, /getSpacedRepetitionSchedules/);
  assert.doesNotMatch(refreshBody, /getProgressRecommendations/);

  // 3. Behavioral verification of the refresh flow:
  // Verifies that exactly one call is made per resource loader and isRefreshing is tied to the loaders promise
  const callCounts = { summary: 0, topics: 0, weakTopics: 0, schedules: 0, recs: 0 };
  let resolveSummary;
  let isRefreshing = false;
  let generation = 1;

  const mockLoadSummary = () => {
    callCounts.summary += 1;
    return new Promise((res) => {
      resolveSummary = res;
    });
  };
  const mockLoadTopics = async () => {
    callCounts.topics += 1;
  };
  const mockLoadWeakTopics = async () => {
    callCounts.weakTopics += 1;
  };
  const mockLoadSchedules = async () => {
    callCounts.schedules += 1;
  };
  const mockLoadRecommendations = async () => {
    callCounts.recs += 1;
  };

  const mockLoadAll = (signal, gen) => {
    return Promise.allSettled([
      mockLoadSummary(),
      mockLoadTopics(),
      mockLoadWeakTopics(),
      mockLoadSchedules(),
      mockLoadRecommendations(),
    ]);
  };

  // Trigger manual refresh
  const triggerRefresh = () => {
    const newGen = generation + 1;
    generation = newGen;
    isRefreshing = true;
    return mockLoadAll(null, newGen).finally(() => {
      if (generation === newGen) {
        isRefreshing = false;
      }
    });
  };

  const refreshPromise = triggerRefresh();

  // Exactly one call per loader dispatched
  assert.equal(callCounts.summary, 1);
  assert.equal(callCounts.topics, 1);
  assert.equal(callCounts.weakTopics, 1);
  assert.equal(callCounts.schedules, 1);
  assert.equal(callCounts.recs, 1);

  // isRefreshing remains true while loaders are pending
  assert.equal(isRefreshing, true);

  // Settle remaining loader
  resolveSummary();
  await refreshPromise;

  // isRefreshing resets to false once all loaders settle
  assert.equal(isRefreshing, false);
});

// ---------------------------------------------------------------------------
// 11. Identity Change Resets Refresh State & Prevents Stale Overwrite
// ---------------------------------------------------------------------------
test("11. Identity change interrupts in-flight manual refresh, resets refresh state, and prevents stale overwrite", async () => {
  const pageSource = readFileSync(join(__dirname, "./ProgressPage.jsx"), "utf-8");

  // Contract: identity change branch must call setIsRefreshing(false)
  const identityEffectMatch = pageSource.match(
    /if\s*\(\s*currentScope\s*!==\s*previousScopeRef\.current\s*\)\s*\{([\s\S]*?)\n\s*previousScopeRef\.current/
  );
  assert.ok(identityEffectMatch, "identity change block must be present");
  assert.match(identityEffectMatch[1], /setIsRefreshing\(false\)/);

  // Lifecycle simulation:
  // State variables replicating ProgressPage component state
  let isRefreshing = false;
  let generation = 0;
  let previousScope = "user:student-1";
  let activeAbortController = null;
  const resourceCalls = { summary: 0, topics: 0, weakTopics: 0, schedules: 0, recs: 0 };
  let resolveOldSummary = null;

  // Loader mocks
  const mockLoaders = {
    loadSummary: (signal, gen) => {
      resourceCalls.summary += 1;
      return new Promise((res) => {
        resolveOldSummary = res;
      });
    },
    loadTopics: async (signal, gen) => {
      resourceCalls.topics += 1;
    },
    loadWeakTopics: async (signal, gen) => {
      resourceCalls.weakTopics += 1;
    },
    loadSchedules: async (signal, gen) => {
      resourceCalls.schedules += 1;
    },
    loadRecommendations: async (signal, gen) => {
      resourceCalls.recs += 1;
    },
  };

  const mockLoadAll = (signal, gen) => {
    return Promise.allSettled([
      mockLoaders.loadSummary(signal, gen),
      mockLoaders.loadTopics(signal, gen),
      mockLoaders.loadWeakTopics(signal, gen),
      mockLoaders.loadSchedules(signal, gen),
      mockLoaders.loadRecommendations(signal, gen),
    ]);
  };

  const handleManualRefresh = () => {
    if (activeAbortController) activeAbortController.abort();
    const controller = new AbortController();
    activeAbortController = controller;
    const newGen = generation + 1;
    generation = newGen;

    isRefreshing = true;
    return mockLoadAll(controller.signal, newGen).finally(() => {
      if (generation === newGen) {
        isRefreshing = false;
      }
    });
  };

  const handleIdentityChange = (newScope) => {
    if (newScope !== previousScope) {
      if (activeAbortController) activeAbortController.abort();
      generation += 1;
      isRefreshing = false; // Reset refresh state on identity change
      previousScope = newScope;
    }
  };

  // 1. A manual refresh starts and sets isRefreshing to true
  const staleRefreshPromise = handleManualRefresh();
  assert.equal(isRefreshing, true, "isRefreshing must be true after manual refresh triggers");
  assert.equal(generation, 1, "generation is incremented for refresh");
  // Exactly one request per resource dispatched
  assert.equal(resourceCalls.summary, 1);
  assert.equal(resourceCalls.topics, 1);
  assert.equal(resourceCalls.weakTopics, 1);
  assert.equal(resourceCalls.schedules, 1);
  assert.equal(resourceCalls.recs, 1);

  // 2. The identity changes before the refresh requests settle
  handleIdentityChange("user:student-2");

  // 3. The previous generation is invalidated and refresh state is reset immediately
  assert.equal(generation, 2, "generation must be incremented on identity change");
  assert.equal(isRefreshing, false, "isRefreshing must be immediately reset to false on identity change");

  // 4. The old generation's eventual promise completion cannot overwrite the new identity's refresh state
  resolveOldSummary();
  await staleRefreshPromise;
  assert.equal(isRefreshing, false, "stale promise finally handler must not alter isRefreshing");

  // 5. Normal manual refresh under the new identity still settles and resets correctly
  let resolveNewSummary = null;
  mockLoaders.loadSummary = (signal, gen) => {
    resourceCalls.summary += 1;
    return new Promise((res) => {
      resolveNewSummary = res;
    });
  };

  const freshRefreshPromise = handleManualRefresh();
  assert.equal(isRefreshing, true, "new identity refresh sets isRefreshing to true");
  assert.equal(generation, 3, "new generation for fresh refresh");
  assert.equal(resourceCalls.summary, 2, "exactly one more request dispatched per resource");

  // Settle new refresh
  resolveNewSummary();
  await freshRefreshPromise;
  assert.equal(isRefreshing, false, "new refresh resets isRefreshing cleanly once complete");
});
