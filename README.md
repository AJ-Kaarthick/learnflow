# LearnFlow


LearnFlow is an AI-powered study workspace that transforms PDF, DOCX, PPTX, and image documents into summaries, flashcards, quizzes, mind maps, and grounded AI conversations using Retrieval-Augmented Generation (RAG).

> AI-powered study workspace for PDFs, DOCX, and PPTX with Retrieval-Augmented Generation (RAG), multi-document chat, summaries, flashcards, quizzes, and mind maps.

---

## Highlights

- Upload and manage PDF, DOCX, and PPTX documents
- Generate AI-powered summaries, flashcards, quizzes, and mind maps
- Resume learning from previously uploaded documents
- Export learning materials as Markdown
- Built with a provider-swappable AI architecture
- Semantic document indexing (RAG foundation)
- Chat with PDF, DOCX, and PPTX documents using RAG
- Multi-turn conversational memory for natural conversations
- Multi-document Chat
- Robust mixed-document Chat handling
- Clear handling of documents with no readable text
- Improved Chat document-library synchronization
- History-aware conversational retrieval for natural follow-up questions
- Persistent AI learning workspace
- AI-generated semantic conversation titles
- Workspace session persistence     
- Per-document conversation history
- Automatic workspace restoration after refresh
- Theme customization (Light / Dark / System)
- Multiple accent color themes
- Workspace personalization
- Accessible UI with persistent appearance preferences
- OCR support for image documents and scanned PDFs
- OCR-based text extraction from supported image documents
- Multi-document Study workspace (1–10 documents with readiness handling)
- Learn Mode with AI-generated curriculum outlines and RAG-grounded topic deep-dives
- Contextual learning controls (Explain, Simplify, Deep Dive, Example; Overview, Standard, In-depth)
- Visualize Mode with interactive concept network knowledge graphs and source citations
- Revision Experience 2.0 with persistent multi-document sessions, deterministic MCQ scoring, and AI open-ended evaluation
- Question != Attempt separation supporting immutable learner response tracking
- Revision session history, in-progress resume, and results review with source document provenance
- Learning Intelligence & Progress workspace (`#/progress`) with 5 dedicated analytics and recommendation endpoints
- Recency-decayed mastery estimation with continuous exponential decay (14-day half-life)
- Weak-topic detection, unbounded struggle index metrics, and topic identity scoped by document
- Spaced repetition review schedules with SM-2 intervals and overdue urgency tracking
- Targeted Revision practice with explicit `topic_focus` and one-click recommendation handoff
- Zero-quota, read-only progress analytics requiring zero database migrations

---

## Features

LearnFlow currently supports:

- 📄 Upload PDF, DOCX, and PPTX documents
- 📑 Extract text from PDF, DOCX, and PPTX documents
- 🔎 OCR-based text extraction from image documents and scanned PDFs
- 🤖 Generate AI-powered summaries
- 🧠 Generate AI-powered flashcards
- 📝 Generate AI-powered quizzes
- 🗺️ Generate AI-powered mind maps
- 📚 Persistent Document Library
- 🔍 Search uploaded documents
- ↕️ Sort documents by name, upload date, or recently opened
- ✏️ Rename documents (with filename validation)
- 🗑️ Delete documents
- 📂 Reopen previously uploaded documents
- 📅 Display upload date and last opened time
- 📄 Display file size
- 📄 Display page count when supported (PDF)
- 📋 Copy summaries, flashcards, and quizzes
- 💾 Download summaries, flashcards, quizzes, and mind maps as Markdown
- 💾 Store generated learning content in SQLite and PostgreSQL
- 🔄 Provider-swappable AI architecture
- 🧩 Semantic document indexing (RAG foundation)
- 🧩 Automatic OCR processing for image-based documents
- 🔎 Semantic search over indexed documents
- 💬 Grounded AI chat with PDF, DOCX, and PPTX documents
- 🧠 Multi-turn conversational memory
- 🧭 History-aware conversational retrieval
- 🏷️ AI-generated conversation titles
- 📚 Multi-document Chat
- 🛡️ Readability-aware multi-document Chat
- ⚠️ Clear identification of documents with no readable text
- 🔄 Automatic Chat document-library refresh after upload
- 📖 Grounded responses with supporting source references
- 💾 Workspace session persistence
- 💬 Per-document conversation history
- 🔄 Multi-document conversation persistence
- 📂 Automatic workspace restoration after refresh
- 🆕 New Conversation for independent chat sessions
- 📑 Persistent study tab selection
- 🎨 Theme customization (Light / Dark / System)
- 🌈 Multiple accent color themes
- ⚙️ Workspace personalization
- 📐 Comfortable & Compact density modes
- ♿ Accessibility improvements
- 🎯 Revision Experience 2.0 with dedicated Revision workspace
- 🗂️ Multi-document Revision covering 1 to 10 documents
- 🤖 AI-generated grounded practice questions (MCQ, Open-ended, Mixed)
- ⚡ Deterministic, zero-quota MCQ evaluation
- 🧠 Rubric-guided AI evaluation for open-ended answers
- 📊 Immutable attempt history and Question != Attempt separation
- 🏆 Official backend session scoring and completion tracking
- 🕒 Revision history list, in-progress session resume, and detailed results review
- 🔍 Per-question source document attribution and frozen evidence snippet citations
- 🛡️ Archived document durability when underlying files are deleted
- 📈 Learner Progress Workspace (`#/progress`) with independent resource cards and retry states
- ⏱️ Continuous exponential recency-decayed mastery estimation (14-day half-life)
- 📊 Continuous daily activity windows (7, 14, and 30 days) and SVG activity chart
- 🎯 Topic mastery tracking scoped strictly by `(document, normalized_topic)`
- ⚠️ Weak-topic detection with unbounded struggle index and actionability safeguards
- 🔁 SM-2 inspired spaced repetition review engine with overdue urgency tracking
- 💡 3-priority adaptive recommendation engine (due spaced review, weak-topic practice, unrevised active documents)
- 🎯 Targeted Revision generation with verifiable evidence grounding and strict fallback
- ⚡ Strict zero-quota, read-only analytics with zero database migrations

---

## Project Status

### ✅ V1.0

- PDF Upload
- Text Extraction
- AI Summaries
- AI Flashcards
- AI Quizzes
- AI Mind Maps

### ✅ V1.1

- UX Improvements
- UI Polish
- Copy & Download Actions
- Persistent Document Manager
- Open Existing Documents
- Cached AI Content
- Refresh-and-Continue Workflow

### ✅ V1.2

#### Milestone 1
- Scrollable Document Library
- Search Documents
- Sort Documents
- Recently Opened
- Improved Filename Validation
- Better Rename Error Handling

#### Milestone 2
- Display Upload Date
- Display Last Opened
- Display File Size
- Display Page Count
- Compact Responsive Metadata Layout

#### Milestone 3

- Markdown Export for Summaries
- Markdown Export for Flashcards
- Markdown Export for Quizzes
- Markdown Export for Mind Maps
- Shared Markdown Export Utilities
- Consistent Download Experience

### ✅ V2.0

#### Milestone 1
- RAG Foundation
- Document Chunking
- Semantic Embeddings
- Document Indexing
- Semantic Search API

#### Milestone 2
- Chat with PDF (Backend)
- Grounded Answer Generation
- Hallucination Prevention
- Chat API
- Source Chunk References

#### Milestone 3
- Chat with PDF Frontend
- Conversation History
- Automatic Document Indexing
- Source Viewer
- Responsive Chat Interface

#### Milestone 4
- Conversational Memory
- Multi-turn Chat
- Conversation History Management
- Automatic History Trimming

#### Milestone 5
- Multi-document Chat
- Compare information across selected documents
- Multi-document grounded retrieval
- Shared conversation across selected documents

#### Milestone 6
- Conversational Retrieval
- Query Condensation
- History-aware Retrieval
- Better Follow-up Questions
- Filename-based Document References
- Improved Chat UX
- Test Isolation Improvements


### ✅ V2.1

#### Milestone 1 
- Redesigned three-panel workspace
- Workspace layout polish
- Improved visual spacing and hierarchy
- Guided empty workspace
- Sticky AI chat composer
- Independent chat scrolling
- Automatic single-document chat synchronization
- Improved multi-document workflow
- Scroll-to-latest button
- Lightweight Markdown rendering
- Browser page scroll prevention
- Responsive layout improvements

#### Milestone 2 
- Workspace session persistence
- Automatic workspace restoration
- Per-document conversation history
- Multi-document conversation persistence
- New Conversation support
- Persistent study tab selection
- Persistent document selection
- Persistent search and sorting
- Library scroll position restoration
- Centralized persistence utility

#### Milestone 3 
- Theme customization
- Light / Dark / System themes
- Multiple accent colors
- Comfortable / Compact density modes
- Workspace personalization
- Persistent appearance settings
- Accessibility improvements
- Reduced motion support
- Final UI polish

#### Milestone 4

- Productivity & Workflow Improvements
- Markdown chat rendering
- GitHub-flavored Markdown support
- Keyboard shortcuts
- Keyboard shortcuts dialog
- Chat timestamps
- Copy AI responses
- Regenerate responses
- Stop generation
- Improved source viewer
- Shared modal component
- Improved chat loading states


### ✅ V2.2

#### Milestone 1 ✅
- DOCX support
- Generic document extraction pipeline
- Document extraction abstraction
- DOCX RAG support
- PDF + DOCX mixed multi-document chat
- Generic upload workflow
- UI polish
- Simplified document header
- Compact document library

#### Milestone 2 ✅

- PPTX support
- Generic presentation extraction
- PPTX RAG support
- PDF + DOCX + PPTX mixed multi-document chat
- Generic document processing pipeline

#### Milestone 3 ✅

- Intelligent multi-document retrieval
- Adaptive retrieval budget
- Balanced retrieval across documents
- Duplicate chunk removal
- Comparison-aware retrieval
- Improved document ranking
- Informative retrieval failures


### ✅ V2.3

#### Milestone 1 ✅

- OCR support for image documents
- OCR support for scanned PDFs
- Generic OCR processing pipeline
- OCR integration with document extraction
- OCR-extracted text integrated with RAG and AI learning features
- OCR dependency detection and diagnostics
- Improved document extraction error logging
- Generated learning content persistence across study-tab switches

### ✅ V2.4

#### Milestone 1 — Chat UX Polish ✅

- Improved multi-document Chat handling
- Readability-aware document selection
- Clear identification of unreadable documents
- Prevented AI generation from documents with no readable text
- Prevented unreadable documents from blocking readable documents
- Improved Chat document-library synchronization after upload
- Preserved existing single- and multi-document Chat behavior
- Improved Chat error handling
- Added regression tests for document readiness and Chat document selection


#### Milestone 2 — Persistent Conversations

##### Phase 1 — Backend Conversation Foundation ✅

- Persistent conversation data model
- Conversation CRUD API
- Conversation-document associations
- Conversation deletion and document-association cleanup

##### Phase 2 — Persistent Message Handling ✅

- Persistent conversation messages
- Conversation-aware RAG chat endpoint
- Database-backed conversation history
- Persistent source and grounding metadata
- Conversation activity tracking
- Transaction-safe message persistence
- Fixed timezone-aware conversation timestamps
- Preserved existing Chat history when selected documents are unreadable
- Fixed Chat uploads replacing existing document selection
- Improved conversation deletion state handling

##### Phase 3 — Frontend Conversation Management ✅

- Conversation list in Chat sidebar
- Conversation switching
- New Conversation workflow
- Conversation deletion from the UI
- Active-conversation fallback after deletion
- Conversation rename support
- Persistent message history restoration
- Persistent conversation document selection
- Conversation timestamp handling
- Chat history preserved when selected documents are unreadable
- Chat document selection preserved when uploading additional documents
- Frontend regression tests for conversation and document-selection behavior

##### Phase 4 — AI Conversation Titles ✅

- AI-generated conversation titles
- Semantic title generation based on conversation intent
- Document context used when helpful for title generation
- Multi-document comparison-aware titles
- Manual conversation rename protection
- Initial-title-only generation
- Title generation failure does not block Chat
- Backend and frontend regression coverage

##### Phase 5 — Dynamic Document Context ✅

- Dynamic document add/remove during conversations
- Persistent conversation document context
- Document context updates without creating a new conversation
- Preserved conversation history while changing document context
- Chat upload synchronization with the current conversation
- Document-selection regression coverage

##### Phase 6 — localStorage Migration ✅

- Removed legacy conversation message caching from localStorage
- Removed legacy per-conversation document caching from localStorage
- Removed legacy multi-document conversation state from localStorage
- Kept only the minimal active-conversation pointer for Chat UI restoration
- Preserved unrelated workspace localStorage persistence
- Added regression coverage preventing reintroduction of legacy conversation caches

##### Phase 7 — Polish / Regression ✅

- Final V2.4 conversation regression review
- Verified conversation creation, switching, deletion, and rename behavior
- Verified AI title generation and manual rename protection
- Verified dynamic document add/remove behavior
- Verified document upload and conversation synchronization
- Verified server-backed conversation persistence
- Added regression coverage for removed-document RAG context
- Backend: 367 tests passing
- Frontend: 93 tests passing
- Frontend production build successful

### 🚧 V3 — In Progress

#### Milestone 1 — Authentication & Guest Access ✅

- Guest mode
- Guest session management
- Sign up / Sign in
- User accounts
- Session management
- Guest usage limits
- Guest → account migration
- User data isolation
- Protected persistent data

##### Phase 1 — Guest Identity & Session Foundation ✅

- Guest identity support
- Guest session cookie
- Guest session persistence across refresh
- Guest identity endpoint
- Browser-level guest identity isolation
- Credentialed frontend API requests
- Guest session expiration handling

##### Phase 2 — Sign Up / Sign In & Credential Validation ✅

- User sign-up
- User sign-in
- Email validation
- Password validation and policy enforcement
- Credential verification
- Invalid-credential error handling
- Authenticated session establishment
- Authenticated identity resolution
- Sign-out support
- Backend and frontend authentication test coverage

##### Phase 3 — Guest Limits + Guest→Account Migration ✅

- Server-enforced guest usage limits
- Guest usage tracking by session
- Guest → account data migration
- Transaction-safe migration
- Guest-session expiration enforcement
- User ownership of migrated documents and conversations
- Backend-enforced user data isolation
- Protected authenticated user data
- Password confirmation validation
- Password visibility controls
- Backend and frontend regression coverage

#### Milestone 2 — Database & User Data Architecture ✅
- PostgreSQL
- User relationships and ownership
- Conversation ownership
- Document ownership
- Revision data model
- SQLite migration
- Database migrations
- Proper data isolation

##### Phase 1 — Database Architecture & Migration Foundation ✅

- Alembic migration framework
- Current V3 schema represented in migration history
- Fresh database initialization through Alembic
- Dialect-aware SQLite/PostgreSQL database configuration
- PostgreSQL compatibility
- Timezone-aware database timestamps
- Legacy SQLite schema drift detection
- Safe handling of legacy databases without false migration stamping
- Preservation of legacy database data
- Migration regression coverage
- PostgreSQL migration compatibility testing

##### Phase 2 — SQLite → PostgreSQL Data Migration & Legacy Schema Reconciliation ✅

- Dedicated administrative migration CLI (`python -m app.db.cli migrate`)
- Migration of legacy V2.4 SQLite to PostgreSQL with required target user ownership
- Migration of modern V3 SQLite to PostgreSQL with preserved ownership
- Physical document file existence validation and target storage synchronization
- Full transactional safety with automatic rollback and copied-file cleanup on failure
- Idempotent reruns with deterministic conflict detection
- Dry-run validation mode (`--dry-run`)
- Comprehensive migration test suite (legacy V2.4, modern V3, type normalization, files, transactions)

##### Phase 3 — Revision Data Model ✅

- Core SQLAlchemy revision models (`RevisionSession`, `RevisionSessionDocument`, `RevisionQuestion`, `RevisionAttempt`)
- Persistent structural separation of Question and Attempt (`Question != Attempt`) supporting multi-attempt history
- Multi-document revision sessions via composite join table
- Top-level session ownership inheritance (`owner_type`, `owner_id`)
- Document deletion decoupling preserving revision history and evidence snapshots
- Guest-to-account revision session ownership transfer
- Alembic migration `74eb271ec556` for SQLite and PostgreSQL

##### Phase 4 — Integration, Isolation & Regression ✅

- End-to-end guest-to-account lifecycle with Revision assets (`test_m2_integration.py`)
- Multi-tenant Revision data isolation across users and guests (`ownership_service.scope_to_owner` and `is_owned_by`)
- Multi-document partial document deletion durability (SET NULL on FK, preserved evidence snapshots & metadata, sister doc preservation)
- Decoupled lifecycle between Conversations and RevisionSessions sharing documents
- Upgraded `sqlite_to_postgres.py` data migration to support modern V3 Revision tables (`revision_sessions`, `revision_session_documents`, `revision_questions`, `revision_attempts`) with UTC timestamps, JSON/JSONB normalization, and composite key conflict handling
- Live PostgreSQL 16 compatibility tests for Revision durability, guest migration, and ownership isolation (`test_postgres_compatibility.py` and `test_sqlite_to_postgres.py`)
- Complete regression verification: 522 backend tests (0 skipped, 0 failed), 159 frontend tests (0 failed), single Alembic head `74eb271ec556`

> **Development database note:** Existing SQLite databases created under the
> pre-Phase-3 schema are not automatically migrated at application startup.
> Legacy V2.4 databases can be migrated to PostgreSQL using the administrative CLI:
> `python -m app.db.cli migrate --sqlite-path ./learnflow.db --postgres-url <url> --target-user-email <email>`.

#### Milestone 3 — Study Experience 2.0 ✅

- Multi-document Study workspace (1–10 documents)
- Document readiness classification and authoritative backend partitioning
- Learn Mode: AI-generated structured curriculum outline
- Learn Mode: RAG-grounded topic explanations with key terms and key takeaways
- Contextual learning actions (Explain, Simplify, Deep Dive, Example)
- Pedagogical depth controls (Overview, Standard, In-depth)
- Grounded source citations and provenance tracking
- Visualize Mode: Interactive concept network knowledge graphs
- Concept nodes, semantic relationship edges, and node inspector
- Bounded graph complexity per depth
- Guest usage tracking and quota enforcement before expensive generation
- Cross-phase integration and full regression coverage

##### Phase 1 — Multi-Document Selection & Study Foundation ✅

- Multi-document Study selection supporting 1 to 10 documents
- Interactive document chip strip with active focus, remove, and add controls
- Readiness classification (readable, unreadable, processing, failed)
- Graceful mixed-readiness handling with explanatory advisory notices
- Persistent study document selection and active tab restoration
- 100% backward compatibility for single-document study tools

##### Phase 2 — Learn Mode Backend Foundation & RAG Grounding ✅

- Curriculum outline endpoint (`POST /api/v1/study/learn/outline`)
- Authoritative backend readiness and ownership partitioning
- RAG-grounded topic endpoint (`POST /api/v1/study/learn/topic`)
- Vector indexing and cross-document chunk retrieval
- Contextual learning actions (Explain, Simplify, Elaborate, Example)
- Pedagogical depth instructions (Overview, Standard, In-depth)
- Guest quota pre-check and post-generation accounting
- Comprehensive backend test coverage (27 tests)

##### Phase 3 — Learn Mode Frontend Experience & Contextual Actions ✅

- Learn tab positioned as the primary Study mode
- Dual-column curriculum layout with collapsible topic units and subtopics
- Topic viewer with Markdown explanation, key terms, takeaways, and citations
- Contextual action bar (Explain, Simplify, Deep Dive, Example, Reset)
- Pedagogical depth selector (Overview, Standard, In-depth)
- Ephemeral session caching preserving variations per topic
- Stale curriculum detection when document selections change
- Responsive layout and theme-aware contrast styling

##### Phase 4 — Visualize Mode & Concept Network Graph ✅

- Visualize tab as the 6th Study mode (`Learn | Summary | Flashcards | Quiz | Mind Map | Visualize`)
- Backend concept graph endpoint (`POST /api/v1/study/visualize/graph`)
- Bounded graph complexity: Overview (10 nodes/15 edges), Standard (16/26), In-depth (22/36)
- D3 force-directed layout computation with pan, zoom, and fit-to-view controls
- Concept node inspector displaying definitions, importance, and connected concepts
- Grounded source citations for central concept nodes
- Category filtering and concept search
- Stale graph detection on selection changes

##### Phase 5 — Final Integration, Regression, QA & Polish ✅

- Cross-phase end-to-end integration test suite (`test_m3_integration.py`)
- Standardized `AIProvider.generate_text` contract across all study features
- Resilient multi-strategy JSON extraction supporting preambles and control characters
- Safe fallback grounding from document snippets when vector chunks are unavailable
- Clean Unicode rendering for list markers, chevrons, and checkmark icons
- Decoupled tab bar from active single-document readiness
- High-contrast semantic tokens across Light/Dark modes and all 4 accent themes
- Complete test suite passing: 558 backend tests, 221 frontend tests, 0 build errors

#### Milestone 4 — Revision Experience 2.0 ✅

- Dedicated Revision workspace (`#/revision`)
- Multi-document Revision covering 1 to 10 documents
- Persistent Revision sessions (`RevisionSession`, `RevisionSessionDocument`, `RevisionQuestion`, `RevisionAttempt`)
- Grounded question generation (MCQ, open-ended, and mixed)
- Deterministic MCQ evaluation (zero AI quota consumed)
- AI-assisted open-ended answer evaluation with rubric criteria
- Immutable attempt history (`Question != Attempt`)
- Official backend session scoring and completion tracking
- Revision history list, in-progress resume, and results review
- Per-question source document provenance and frozen evidence citations
- Document deletion durability with graceful archived document fallback
- Guest lifecycle support, quota enforcement, and guest-to-account migration

##### Phase 1 — Revision Session Creation & Question Generation Backend ✅
- Revision REST API router (`POST /api/v1/revision/sessions`, `GET /api/v1/revision/sessions`, `GET /api/v1/revision/sessions/{id}`)
- Multi-document readiness validation and proportional character budgeting
- Grounded prompt construction and resilient JSON question extraction
- Atomic session and question persistence with ownership scoping
- Guest AI generation quota pre-check and post-generation accounting
- Comprehensive Phase 1 test suite (24 tests)

##### Phase 2 — Answer Evaluation Engine & Attempt Tracking Backend ✅
- Question attempt endpoint (`POST /api/v1/revision/sessions/{session_id}/questions/{question_id}/attempts`)
- Deterministic, zero-quota MCQ evaluator normalizing strings, indices, and letter labels
- Rubric-guided AI evaluator for open-ended answers with structured JSON scoring
- Atomic `RevisionAttempt` record persistence with attempt numbers and timestamps
- Authoritative session completion endpoint (`POST /api/v1/revision/sessions/{session_id}/complete`)
- Comprehensive Phase 2 test suite (23 tests)

##### Phase 3 — Frontend Revision Workspace & Active Session Runner ✅
- Dedicated Revision top-level route and navigation bar link (`#/revision`)
- Interactive setup launcher with multi-document selection (1–10 docs), modes, and difficulties
- Active session runner with keyboard shortcuts, timer, and question navigation dots
- Interactive MCQ option selection and open-ended text answer composer
- Immediate post-submission feedback cards with score, correct answer, explanation, and evidence
- Attempt retries with immutable history accumulation

##### Phase 4 — Session History, Results Review, Resume & Multi-Document Polish ✅
- Revision history list with session cards displaying score, status, date, and document chips
- In-progress session resume jumping directly to the first unattempted question
- Completed results review mode displaying official score and question-by-question outcomes
- Per-question attempt timeline showing all historical attempts
- Provenance viewer with source document attribution and frozen evidence quotes
- Graceful rendering of deleted source documents as "Archived Document"
- "Retake Revision" action pre-filling setup configuration for a fresh session

##### Phase 5 — Cross-Phase Integration, Guest Migration, QA & Documentation ✅
- End-to-end cross-phase integration test suite (`test_m4_integration.py`)
- Verified guest-to-account migration preserving revision sessions, questions, and attempts
- Verified document deletion durability (`ON DELETE SET NULL` + frozen evidence citations)
- Verified multi-document provenance isolation and cross-identity access control
- Verified guest AI quota accounting (0 for MCQ, 1 for open-ended on success)
- Full automated test suite passing: 612 backend tests, 288 frontend tests, clean production build

#### Milestone 5 — Learning Intelligence & Progress 🟡

*Status: Implementation, automated verification, and manual browser QA complete — release publication pending.*

- Dedicated Learner Progress workspace (`#/progress`)
- 5 read-only, zero-quota REST analytics endpoints (`/progress/*`)
- Exponential recency-decayed mastery estimation (14-day half-life continuous decay)
- Topic mastery tracking scoped strictly by `(document_identity, normalized_topic_key)`
- Weak-topic detection with struggle index and document readiness actionability safeguards
- Spaced repetition review schedules with SM-2 inspired intervals and overdue urgency tracking
- 3-priority adaptive recommendation engine (`spaced_review`, `weak_topic_practice`, `unrevised_document`)
- Targeted Revision practice with explicit `topic_focus`, verifiable evidence grounding, and atomic rollback
- One-click launch handoff from Progress recommendations to Revision setup
- Durability across document deletion (`ON DELETE SET NULL`) and guest-to-account migration
- Zero database migrations (Alembic head `74eb271ec556` preserved)

##### Phase 1 — Mastery Estimation & Progress Analytics Foundation Backend ✅
- Exponential recency-decay weighting with 14-day half-life ($\lambda \approx 5.73 \times 10^{-7} \text{ s}^{-1}$)
- 3-question minimum threshold: assessed ($N \ge 3$) vs unassessed ($N < 3$)
- 4 mastery tiers: `mastered` ($\ge 0.85$), `proficient` ($0.70 \le s < 0.85$), `needs_practice` ($< 0.70$), `unassessed`
- Progress endpoints: `GET /api/v1/progress/summary` and `GET /api/v1/progress/topics`
- Daily activity buckets over continuous 7-, 14-, and 30-day windows
- Topic provenance isolation preventing conflation across distinct documents

##### Phase 2 — Weak-Topic Detection, Spaced Repetition & Adaptive Scheduling Backend ✅
- Weak-topic detection endpoint `GET /api/v1/progress/weak-topics`
- Unbounded struggle index: $\text{Struggle} = (1.0 - \text{Mastery}) \times \ln(1 + \text{Total Attempts}) \times \text{Incorrect Ratio}$
- Spaced repetition schedule endpoint `GET /api/v1/progress/spaced-repetition`
- SM-2 inspired review progression (1, 3, 7, 14, 30 days) with raw review average thresholding (0.70)
- Overdue urgency calculation ($\text{Urgency} = \Delta t / \text{interval}$) and review due date projections
- Actionability gated strictly on live, ready documents with usable extracted text

##### Phase 3 — Adaptive Recommendation Engine & Progress REST APIs ✅
- Recommendation endpoint `GET /api/v1/progress/recommendations` with 3-priority hierarchy:
  1. `spaced_review` (urgency $\ge 1.0$)
  2. `weak_topic_practice` (struggle index and mastery)
  3. `unrevised_document` (active ready documents never revised)
- Action payloads containing pre-configured Revision parameters (`document_ids`, `mode`, `difficulty`, `question_count`, `topic_focus`)
- Targeted Revision backend support via `topic_focus` in `POST /api/v1/revision/sessions`
- AI topic support confirmation protocol (`topic_supported: true/false`) and verifiable evidence extraction
- Atomic failure rollback on unsupported topic (HTTP 422), malformed output (HTTP 502), or unverifiable quotes
- Retake preparation preserving `topic_focus` without auto-starting

##### Phase 4 — Learner Progress Workspace & Recommendation Actions ✅
- Dedicated Progress workspace route (`#/progress`) and top-level navigation link
- Metric overview cards with honest schemas (percentages, `--` for unassessed, decimal struggle index)
- Responsive SVG activity chart with volume bars, continuous polyline, and missing-data gaps
- Activity timeline score marker coordinate anchoring: eliminated SVG root-origin scaling (`hover:scale-125`) in favor of direct data-anchored styling and non-displacing color transitions, keeping markers strictly inside plot bounds
- Topic mastery table with tier badges, attempt counts, and document titles
- Weak-topic cards with struggle metrics and "Practice Weak Topic" action buttons
- Spaced repetition review list with urgency badges, streaks, and "Review Now" action buttons
- Priority recommendation cards with one-click Revision handoff
- Independent resource loading states, per-section retry without discarding successful endpoints
- Generation guard and identity isolation aborting old requests on identity change

##### Phase 5 — Cross-Phase Integration, Guest Migration, QA & Documentation ✅
- Comprehensive cross-phase integration test suite (`backend/tests/test_m5_integration.py`, 17 tests) covering all 5 progress endpoints against shared learning history
- Targeted Revision generation and atomic failure mode verification (HTTP 422 unsupported topic rejection, mock AI verification)
- Verified guest-to-account migration preserving revision sessions, questions, attempts, and progress visibility
- Verified document deletion durability (`ON DELETE SET NULL`) and title collision safety
- Phase 4 workspace contract and zero-quota regression verification
- Activity-chart hover/marker regression resolved and covered by automated frontend contract and coordinate bounding tests
- Full automated test suite passing: 726 backend tests (5 skipped — PostgreSQL-specific tests skipped when `POSTGRES_TEST_DATABASE_URL` is unset), 321 frontend tests, clean production build
- Manual browser QA passed: Activity timeline score markers stay strictly anchored during hover, and Progress dashboard updates dynamically across session completion and page reloads
- Milestone 5 complete — release publication (`v3.0.0-m5`) pending user authorization

#### Milestone 6 — Home & Personalized Dashboard
- Continue where you left off
- Progress summary
- Recommended next actions
- Weak areas
- Recent activity
- Personalized quick actions
- Guest and signed-in home states

#### Milestone 7 — Sharing & Learning Material Export
- Share revision results
- Share Study-generated material
- Share Chat content
- Clean text export
- Native sharing
- WhatsApp/social sharing
- Shareable links
- Privacy controls

#### Milestone 8 — Production & Deployment
- Docker
- Production configuration
- PostgreSQL production setup
- Storage abstraction
- Object storage support
- Secure authentication
- Authorization and user isolation
- Production testing
- Health checks and observability
- Deployment
- Backup and recovery

---

## Running Locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Add your Gemini API key to `.env`:

```env
GEMINI_API_KEY=your_api_key
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

Run the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Run backend tests:

```bash
pytest
```

---

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Tech Stack

### Frontend
- React
- Vite
- Tailwind CSS

### Backend
- FastAPI
- Python
- SQLAlchemy
- Alembic
- SQLite (development & testing)
- PostgreSQL (V3 persistent database architecture)

### AI
- Gemini
- Retrieval-Augmented Generation (RAG)
- Provider abstraction layer

---

## Documentation

- `docs/architecture.md`
- `docs/DEVLOG.md`

---


## Roadmap

### Completed
- AI-generated learning content
- Persistent document library
- Retrieval-Augmented Generation (RAG)
- Grounded AI chat
- Conversational Memory
- Multi-document Chat
- History-aware Conversational Retrieval
- Workspace UX Polish
- Workspace Session Persistence
- Workspace Personalization
- OCR document processing
- Intelligent multi-document retrieval
- Chat UX and document-readiness improvements
- Improved Chat document-library synchronization
- Persistent conversation backend foundation
- Persistent conversation backend
- Persistent conversation messages
- AI-generated semantic conversation titles
- Dynamic conversation document context
- localStorage conversation-state migration
- V3 guest identity and session foundation
- V3 email/password authentication
- V3 guest usage limits
- V3 guest-to-account migration
- V3 user data isolation
- V3 M2 database migration foundation
- Alembic schema migration infrastructure
- SQLite/PostgreSQL database compatibility foundation
- Legacy SQLite schema drift detection
- SQLite → PostgreSQL data migration CLI and storage synchronization
- Persistent Revision data model foundation (sessions, questions, attempts)
- V3 Milestone 3 — Study Experience 2.0 (Learn Mode & Visualize Mode)
- V3 Milestone 4 — Revision Experience 2.0 (Sessions, Attempt Tracking, Results Review)

### In Progress / Awaiting Release

- V3 Milestone 5 — Learning Intelligence & Progress (Implementation, automated verification, and manual browser QA complete — release publication pending)

### Planned

- V3 Milestone 6 — Home & Personalized Dashboard
- V3 Milestone 7 — Sharing & Learning Material Export
- V3 Milestone 8 — Production & Deployment