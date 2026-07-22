# LearnFlow Development Log

---

# Milestone 0 — Project Scaffolding

**Date:** 11 July 2026

## Objective

Create a production-style project structure and verify the backend and frontend communicate successfully.

## Completed

- Created GitHub repository
- Cloned repository locally
- Set up FastAPI backend
- Set up React + Vite frontend
- Configured Tailwind CSS
- Created Python virtual environment
- Installed backend dependencies
- Installed Node.js using nvm
- Installed frontend dependencies
- Verified `/health` endpoint
- Verified frontend successfully communicates with backend

## Learned

- Python virtual environments
- FastAPI project structure
- React + Vite basics
- Tailwind CSS setup
- Git workflow
- Node Version Manager (nvm)
- Environment variables (.env)

## Problems Faced

1. Missing `python3-venv`
2. Git safe.directory warning
3. Node.js v18 incompatible with Vite 8

## Solutions

- Installed `python3.12-venv`
- Configured Git safe.directory
- Installed Node.js LTS using nvm

## Reflection

Milestone 0 taught me that setting up a development environment is a significant part of software engineering. Most issues encountered were related to tooling rather than application code. I now have a working full-stack project foundation that future milestones will build upon.

---

# Milestone 1

## Goal

Implement PDF upload and text extraction.

## Features Completed

- Upload PDF from the React frontend
- Store uploaded PDFs locally
- Extract text using pypdf
- Store document metadata in SQLite
- Retrieve uploaded document by ID
- Display extracted text preview
- Added automated backend tests

## Learned

- FastAPI routing
- SQLAlchemy ORM basics
- File upload using FormData
- React API layer
- Service layer architecture
- SQLite integration
- Backend ↔ Frontend communication

## Problems Faced

- Duplicate backend folder after copying milestone
- Git ignored files verification
- Backend testing and routing verification

## Result

LearnFlow can now upload PDFs, extract their text, store metadata, and display the extracted content through the React frontend.

---

# Milestone 2

## Goal

Implement AI-powered document summarization using a reusable AI architecture.

## Features Completed

- AI-generated summaries
- Gemini integration
- AI provider abstraction
- Summary caching
- Summary API endpoints
- Frontend summary generation
- Backend tests for summarization

## Learned

- Provider abstraction
- Dependency injection
- Environment variables
- AI service architecture
- Summary caching

## Problems Faced

- Gemini model deprecation
- API key accidentally added to `.env.example`
- Dependency version mismatch after SDK upgrade

## Solutions

- Updated to a supported Gemini model
- Removed the exposed API key before committing
- Updated dependencies and verified a clean installation

## Result

LearnFlow can now generate AI summaries while keeping the AI layer modular and reusable for future features like flashcards, quizzes, and document chat.

---

# Milestone 3

## Goal

Implement AI-generated flashcards while reusing the AI infrastructure built in Milestone 2.

## Features Completed

- AI-generated flashcards
- Flashcard database model
- Flashcard caching
- Flashcard API endpoints
- Frontend flashcard generation
- Backend tests for flashcards

## Learned

- Prompting LLMs for structured JSON
- JSON parsing and validation
- Reusing existing service architecture
- Designing reusable AI features

## Problems Faced

- Handling AI responses wrapped in Markdown code fences
- Validating malformed JSON responses
- Reusing existing architecture without duplicating logic

## Result

LearnFlow can now generate and cache AI-powered flashcards while reusing the same provider abstraction introduced in Milestone 2.

---

# Milestone 4

## Goal

Implement AI-generated quizzes while reusing the AI infrastructure built in previous milestones.

## Features Completed

- AI-generated quizzes
- Quiz database model
- Quiz caching
- Quiz API endpoints
- Frontend quiz generation
- Shared structured-output parser
- Backend tests for quizzes

## Learned

- Reusing common parsing logic
- Database design tradeoffs
- JSON columns in SQLAlchemy
- Extending existing architecture without duplication

## Problems Faced

- Designing a reusable JSON parser for multiple AI features
- Choosing between normalized tables and JSON columns
- Keeping the AI provider abstraction generic

## Result

LearnFlow can now generate, cache, and display AI-powered quizzes while reusing the same AI provider abstraction and shared structured-output utilities used by other AI features.

---

# Milestone 5

## Goal

Implement AI-generated mind maps while continuing to reuse the existing AI architecture.

## Features Completed

- AI-generated mind maps
- Mind map database model
- Mind map caching
- Mind map API endpoints
- Interactive frontend visualization
- Shared structured-output utilities
- Backend tests for mind maps

## Learned

- Representing hierarchical data as trees
- Tree validation
- JSON storage for hierarchical structures
- Choosing between JSON storage and normalized database tables
- Reusing existing architecture without introducing new AI abstractions

## Problems Faced

- Choosing an appropriate data structure for mind maps
- Rendering hierarchical AI output on the frontend
- Keeping the implementation reusable while avoiding unnecessary complexity

## Result

LearnFlow V1 is now feature complete. Users can upload PDFs and generate summaries, flashcards, quizzes, and interactive mind maps while reusing a single AI provider abstraction and a shared architecture across all AI features.

---

# V1.1 — Milestone 1

## Goal

Improve the user experience without changing the project's architecture or adding new AI features.

## Features Completed

- Cleared previous AI-generated content after uploading a new document
- Added loading indicators for uploads and AI generation
- Disabled controls while requests were running
- Added user-friendly status and error messages
- Added empty states to AI panels
- Added client-side PDF validation
- Fixed same-file upload support
- Fixed a React reconciliation bug affecting panel resets during sequential uploads

## Learned

- React component remounting using keys
- React reconciliation and sibling key uniqueness
- Client-side validation versus backend validation
- Improving UX without changing business logic
- Importance of browser-based smoke testing in addition to backend testing

## Problems Faced

- Previous AI-generated content persisted after uploading a new document.
- React components were not resetting correctly because sibling components shared identical keys.
- Initial smoke tests only verified backend behavior and did not exercise React reconciliation.

## Solutions

- Assigned unique keys to each AI panel by combining the panel type with the document ID.
- Improved frontend validation and loading behavior.
- Added browser-level verification for sequential document uploads.

## Verification

- Backend tests: **40 passed**
- Frontend production build successful
- Manual smoke testing completed
- Sequential uploads verified
- Same-file upload verified
- Client-side validation verified

## Result

LearnFlow now provides a significantly smoother user experience while preserving the original architecture. The application correctly resets AI panels between uploads, provides immediate user feedback during long-running operations, and handles common user interactions more reliably.

---

# V1.1 — Milestone 2

## Goal

Improve the visual quality and usability of LearnFlow without changing its architecture or functionality.

## Features Completed

- Introduced a consistent accent color system
- Redesigned AI panels using reusable card styling
- Improved typography and visual hierarchy
- Unified button styling across the application
- Improved responsive layout for desktop and mobile
- Added keyboard focus indicators
- Improved quiz accessibility with icon + text feedback
- Improved flashcard interaction hints

## Learned

- Building a consistent design system
- Responsive UI design using Tailwind CSS
- Accessibility fundamentals
- Maintaining visual consistency across components
- Improving UI without modifying application architecture

## Problems Faced

- CSS comment syntax caused a production build failure.
- Mobile devices do not support hover interactions.
- Browser-based verification was required because jsdom cannot fully render SVG layouts.

## Solutions

- Fixed the CSS parsing issue and rebuilt successfully.
- Updated flashcard hints to work for both touch and desktop users.
- Verified the layout through automated smoke tests and manual browser testing.

## Verification

- Backend tests: **40 passed**
- Frontend production build successful
- Manual browser testing completed
- Responsive layout verified
- Accessibility improvements verified

## Result

LearnFlow now provides a cleaner, more consistent, and more accessible interface while preserving the original architecture and functionality.

---

# V1.1 — Milestone 3A

## Goal

Improve the usability of generated learning content by allowing users to easily copy or download AI-generated outputs.

## Features Completed

- Added Copy action for AI summaries
- Added Download Summary (.txt) support
- Added Copy action for flashcards
- Added Copy action for quizzes
- Added transient "Copied!" and "Downloaded!" feedback
- Buttons only appear when content exists
- Disabled actions while generation is in progress

## Learned

- Browser Clipboard API
- File downloads using Blob and object URLs
- Providing lightweight user feedback without extra dependencies
- Designing convenience features while preserving existing architecture

## Problems Faced

- Test harness mocked the wrong global URL object during download testing.
- Clipboard functionality behaves differently depending on browser permissions and secure contexts.

## Solutions

- Corrected the test harness to mock the appropriate global object.
- Implemented graceful failure handling for clipboard operations without affecting the user experience.

## Verification

- Backend tests: **40 passed**
- Frontend production build successful
- Browser smoke testing completed
- Copy functionality verified
- Download functionality verified

## Result

LearnFlow now allows users to easily reuse AI-generated content by copying summaries, flashcards, and quizzes or downloading summaries as text files, without changing the existing application architecture.

---

# V1.1 — Milestone 3B

**Date:** 21 July 2026

## Goal

Transform LearnFlow into a persistent document workspace by introducing a Document Manager.

## Features Completed

- Added document history
- Open previously uploaded documents
- Restored cached summaries, flashcards, quizzes and mind maps
- Added document renaming
- Added document deletion
- Centralized cached-content loading in HomePage
- Added backend tests for document management

## Learned

- Coordinating application state from a higher-level React component
- Designing RESTful CRUD endpoints
- Building persistent user workflows
- Separating backend state from UI state

## Problems Faced

- ORM relationships did not automatically cascade deletes.
- Component-level data fetching would have scattered application state.
- React controlled-input behaviour required adjustments during testing.

## Solutions

- Explicitly deleted associated AI-generated data and uploaded files.
- Centralized document loading in HomePage.
- Expanded backend tests and browser-level smoke testing.

## Verification

- Backend tests: **48 passed**
- Frontend production build successful
- Browser smoke testing completed
- Document restore verified
- Rename verified
- Delete verified

## Result

LearnFlow now behaves as a persistent AI learning workspace where users can return to previously uploaded documents and continue learning without regenerating AI content.

### Post-Milestone Improvements

- Improved document rename UX by preserving the original file extension while preventing extension changes.
- Generalized filename handling to support future document types.
- Added generic filename utilities and additional backend tests.