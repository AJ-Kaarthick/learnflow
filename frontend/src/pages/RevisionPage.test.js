import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// RevisionPage Component Contracts (V3 Milestone 6 Phase 2)
// ---------------------------------------------------------------------------

test("1. RevisionPage.jsx imports and consumes pending resume token", () => {
  const source = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*consumePendingRevisionResume[^}]*\}\s*from\s*"\.\.\/utils\/revisionState/);
  assert.match(source, /consumePendingRevisionResume\(identity\)/);
});

test("2. RevisionPage.jsx retrieves existing session via getRevisionSession on resume", () => {
  const source = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  assert.match(source, /import\s*\{[^}]*getRevisionSession[^}]*\}\s*from\s*"\.\.\/api\/revision/);
  assert.match(source, /getRevisionSession\(pendingResume\.sessionId\)/);
});

test("3. RevisionPage.jsx routes in_progress session to active runner without creating duplicate session", () => {
  const source = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  // In-progress session enters existing runner via handleResumeSession
  assert.match(source, /session\.status === "in_progress"/);
  assert.match(source, /handleResumeSession\(session\)/);

  // handleResumeSession restores persisted detail without calling createRevisionSession
  const resumeFnMatch = source.match(/function handleResumeSession\(sessionDetail\)\s*\{([\s\S]*?)\}/);
  assert.ok(resumeFnMatch);
  assert.doesNotMatch(resumeFnMatch[1], /createRevisionSession/);
  assert.match(resumeFnMatch[1], /setActiveSession\(sessionDetail\)/);
  assert.match(resumeFnMatch[1], /setViewMode\("runner"\)/);
});

test("4. RevisionPage.jsx routes already-completed session to results review gracefully", () => {
  const source = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  assert.match(source, /session\.status === "completed"/);
  assert.match(source, /handleReviewSession\(session\)/);
});

test("5. RevisionPage.jsx provides accessible resuming indicator and dismissible error banner", () => {
  const source = readFileSync(join(__dirname, "./RevisionPage.jsx"), "utf-8");

  // Resuming indicator
  assert.match(source, /data-testid="revision-resuming-indicator"/);
  assert.match(source, /Resuming revision session\.\.\./);

  // Dismissible error banner
  assert.match(source, /role="alert"/);
  assert.match(source, /setResumeError\(null\)/);
});
