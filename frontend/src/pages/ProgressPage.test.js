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

  // Scope change detection immediately resets all 5 resource states
  assert.match(pageSource, /currentScope\s*!==\s*previousScopeRef\.current/);
  assert.match(pageSource, /setSummaryState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setTopicsState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setWeakTopicsState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setSchedulesState\(\{\s*data:\s*null/);
  assert.match(pageSource, /setRecommendationsState\(\{\s*data:\s*null/);

  // In-flight abort & generation increment on identity change
  assert.match(pageSource, /abortControllerRef\.current\.abort\(\)/);
  assert.match(pageSource, /generationRef\.current\s*\+=\s*1/);

  // Auth loading gate: early return without firing network requests
  assert.match(pageSource, /authStatus\s*===\s*"loading"\s*\|\|\s*!currentScope/);

  // Render isolated shell while resolving identity (no stale user data)
  assert.match(pageSource, /Resolving identity\.\.\./);
});
