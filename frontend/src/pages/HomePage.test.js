import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

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
