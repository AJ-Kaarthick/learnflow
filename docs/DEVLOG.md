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


# V1.2 — Milestone 1

## Goal

Improve document management for projects with many uploaded PDFs.

## Features Completed

- Added Document Library
- Search by filename
- Sort by name
- Sort by upload date
- Sort by recently opened
- Fixed-height scrollable library
- Result count
- Empty search state
- Added last_opened tracking
- Improved rename validation
- Duplicate filename prevention
- Better rename error handling

## Learned

- Designing scalable document management
- Server-side search vs client-side search
- REST query parameters
- Backend validation vs frontend validation
- Better UX for inline form validation

## Problems Faced

- Growing document list pushed AI content down the page.
- Duplicate filenames created ambiguity.
- Rename errors were not visible to the user.

## Solutions

- Introduced a scrollable Document Library.
- Added server-side search and sorting.
- Added case-insensitive duplicate detection.
- Added inline rename validation messages.

## Verification

- Backend tests: **85 passed**
- Frontend production build successful
- Manual browser testing completed
- Search verified
- Sorting verified
- Recently Opened verified
- Rename validation verified

## Result

LearnFlow now scales much better for users with many uploaded documents. The new Document Library keeps AI content accessible while making it easy to search, organize, and manage previously uploaded PDFs.

---

# V1.2 — Milestone 2

## Goal

Improve the Document Library by displaying useful document metadata while preserving the existing architecture.

## Features Completed

- Display upload date
- Display last opened date
- Display file size
- Display page count
- Compact responsive metadata layout
- Stored file size during upload
- Stored page count during upload
- Added backend tests for new metadata

## Learned

- Tradeoffs between deriving metadata and storing it
- Extending SQLAlchemy models safely
- Keeping UI improvements isolated from business logic
- Maintaining backward compatibility with additive API changes

## Problems Faced

- Existing SQLite database schema did not include the new columns.
- Existing databases are not updated automatically by `Base.metadata.create_all()`.

## Solutions

- Added nullable database columns for `file_size_bytes` and `page_count`.
- Populated metadata during document upload.
- Recreated the local development database to apply the updated schema.

## Verification

- Backend tests: **86 passed**
- Frontend production build successful
- Manual browser testing completed
- Upload date verified
- Last opened verified
- File size verified
- Page count verified
- Search, sort, rename and delete regression testing completed

## Result

LearnFlow now provides richer document information while preserving the existing architecture. Users can quickly identify documents using upload date, last opened time, page count and file size without affecting existing functionality.

---

# V1.2 — Milestone 3

## Goal

Improve the usability of AI-generated learning content by allowing users to export every generated artifact in Markdown format.

## Features Completed

- Markdown export for summaries
- Markdown export for flashcards
- Markdown export for quizzes
- Markdown export for mind maps
- Added shared frontend download utility
- Added shared Markdown export utilities
- Reused existing mind map Markdown conversion

## Learned

- Reusing frontend utilities instead of duplicating logic
- Designing reusable Markdown formatting helpers
- Separating formatting logic from UI components
- Maintaining a consistent export experience across different data structures

## Problems Faced

- Each learning artifact had a different internal data structure.
- Export functionality needed to remain consistent without introducing duplicated code.

## Solutions

- Created shared download and Markdown formatting utilities.
- Reused the existing `treeToMarkdown` function for mind map export.
- Kept all export logic on the frontend since the generated content already exists in client state.

## Verification

- Manual browser testing completed
- Summary export verified
- Flashcard export verified
- Quiz export verified
- Mind map export verified
- Copy functionality regression tested
- Search, sort, rename, and delete regression tested

## Result

LearnFlow now allows users to export every generated learning artifact as Markdown while preserving the existing architecture and maintaining a consistent user experience.

# V2 — Milestone 1

Goal:

Implement the Retrieval-Augmented Generation (RAG) foundation required for future conversational AI features.

Features Completed

- Document chunking
- DocumentChunk database model
- Embedding provider abstraction
- Gemini embedding implementation
- Document indexing endpoint
- Semantic search endpoint
- Retrieval service
- Chunking service
- Embedding service
- Backend tests

Learned

- Retrieval-Augmented Generation (RAG)
- Embedding vectors
- Semantic search
- Cosine similarity
- Chunking strategies
- Provider abstraction for embeddings

Problems Faced

- Chunk boundary produced partial words
- Choosing a storage format for embedding vectors
- Deciding between brute-force retrieval and vector databases

Solutions

- Adjusted chunk boundaries to respect word limits
- Stored embeddings as JSON in SQLite
- Used brute-force cosine similarity for simplicity and current project scale

Verification

This is where your manual testing goes.

## Verification

- Backend tests: **104 passed**
- Manual API testing completed
- Document indexing verified
- Semantic search verified
- Duplicate indexing verified
- Existing V1 functionality regression tested

Result

LearnFlow now includes a complete Retrieval-Augmented Generation foundation capable of indexing documents and retrieving semantically relevant chunks. This infrastructure will power future conversational features such as Chat with PDF.


# V2 — Milestone 2

Goal:

Implement Chat with PDF by combining semantic retrieval with grounded AI-generated answers.

## Features Completed

- Chat service
- Chat API endpoint
- Grounded answer generation
- Prompt construction using retrieved chunks
- Hallucination prevention
- Reused existing RetrievalService
- Reused AI provider abstraction
- Backend tests

## Learned

- Retrieval-Augmented Generation workflow
- Prompt grounding
- Separating retrieval from generation
- Designing extensible chat APIs
- Hallucination mitigation techniques

## Problems Faced

- Preventing answers outside the retrieved document context
- Designing reusable chat response schemas
- Maintaining architectural consistency with existing services

## Solutions

- Constructed prompts only from retrieved chunks
- Reused existing retrieval and AI provider layers
- Reused existing SearchResultItem schema for chat sources

## Verification

- Backend tests: **114 passed**
- Manual API testing completed
- Chat endpoint verified
- Grounded answers verified
- Hallucination prevention verified
- Existing V1 and V2 regression testing completed

## Result

LearnFlow now supports grounded question answering over indexed PDF documents. The chat system combines semantic retrieval with the existing AI provider architecture to answer questions using only the uploaded document while returning supporting source chunks for transparency.


## V2 — Milestone 3

Goal:

Implement a frontend chat interface for grounded conversations with uploaded PDF documents.

## Features Completed

- Chat panel
- Chat API integration
- Local conversation history
- Automatic document indexing
- Source viewer
- Loading indicators
- Empty state
- Friendly error handling
- Automatic conversation reset when switching documents

## Learned

- Designing conversational user interfaces
- React state management for chat applications
- Reusing existing API abstraction layers
- Component remounting using React keys
- Building responsive chat layouts

## Problems Faced

- Integrating chat without affecting existing features
- Resetting conversation state when changing documents
- Presenting supporting source chunks in a readable way

## Solutions

- Reused the existing frontend API layer
- Used React's keyed remount pattern to automatically reset conversations
- Displayed supporting chunks inside expandable source panels

## Verification

- Backend tests: **114 passed**
- Frontend production build successful
- Manual browser testing completed
- Chat responses verified
- Conversation history verified
- Automatic indexing verified
- Hallucination prevention verified
- Source display verified
- Document switch reset verified
- Existing feature regression testing completed

## Result

LearnFlow now provides a complete end-to-end conversational experience. Users can upload PDFs, generate learning material, and ask grounded questions through a responsive chat interface while reusing the existing Retrieval-Augmented Generation architecture.

# V2 — Milestone 4

Goal:

Implement conversational memory to support natural multi-turn conversations while preserving grounded Retrieval-Augmented Generation.

## Features Completed

Multi-turn conversational memory
Conversation history support in Chat API
Client-managed conversation history
Automatic history trimming
Context-aware prompt construction
Frontend history integration
Backend tests for conversational memory

## Learned

Conversational AI design
Stateless chat architectures
Prompt engineering using conversation history
Tradeoffs between frontend-managed and backend-managed memory
Context window management

## Problems Faced

Resolving follow-up questions without storing conversations in the backend
Preventing unlimited conversation growth
Preserving hallucination prevention while introducing conversational context
Solutions
Sent recent conversation history with every chat request
Trimmed conversation history before prompt construction
Continued grounding answers only with retrieved document chunks
Kept the backend stateless by managing conversation history in the frontend

## Verification

Backend tests: 121 passed
Frontend production build successful
Manual browser testing completed
Multi-turn conversations verified
Conversation reset verified
Hallucination prevention regression tested
Source references verified
Existing feature regression testing completed

## Result

LearnFlow now supports natural multi-turn conversations over uploaded PDF documents while preserving the existing Retrieval-Augmented Generation architecture. Users can ask follow-up questions without repeating previous context, and all responses remain grounded in retrieved document content.

# V2 — Milestone 5

## Goal

Extend Chat with PDF to support grounded conversations across multiple selected documents while preserving the existing Retrieval-Augmented Generation architecture.

## Features Completed

- Multi-document chat
- Multi-document retrieval
- Multi-document chat API
- Document selection in the frontend
- Shared conversation across selected documents
- Retrieval from multiple indexed documents
- Backend tests

## Learned

- Multi-document Retrieval-Augmented Generation
- Balancing retrieval across multiple documents
- Reusing existing retrieval services without architectural duplication
- Extending APIs while preserving backward compatibility

## Problems Faced

- Designing retrieval across multiple documents
- Preserving grounded answers when multiple sources are selected
- Ensuring retrieval remained document-balanced

## Solutions

- Extended the retrieval pipeline to support multiple document IDs
- Reused the existing retrieval service and prompt builder
- Preserved the stateless backend and client-managed conversation history

## Verification

- Backend tests: **133 passed**
- Frontend production build successful
- Manual browser testing completed
- Multi-document conversations verified
- Single-document regression testing completed
- Compare and summarization workflows verified

## Result

LearnFlow now supports grounded conversations across multiple selected documents while preserving the existing Retrieval-Augmented Generation architecture. Each selected document participates in semantic retrieval, allowing users to summarize, compare, and discuss multiple PDFs within a single conversation.


# V2 — Milestone 6

## Goal:

Improve conversational Retrieval-Augmented Generation by enabling history-aware retrieval while preserving the existing architecture and hallucination prevention.

## Features Completed

Conversational retrieval
Query condensation
History-aware retrieval
Filename-based document references
Improved chat UX
Backend regression tests
Test isolation improvements

## Learned

Query rewriting vs conversational retrieval
History-aware semantic retrieval
Separating retrieval from generation
Regression testing AI workflows
Test isolation using temporary databases
UX trade-offs in conversational interfaces

## Problems Faced

Follow-up questions such as "Explain it." retrieved irrelevant chunks because retrieval only saw the current turn.
Generic document references ("Document 1") reduced answer readability.
Chat panel scrolled unexpectedly during document selection.
Backend tests polluted the development database across repeated runs.

## Solutions

Added query condensation before retrieval.
Preserved the original user question for generation.
Used filenames in grounded responses.
Prevented chat auto-scroll on initial mount.
Isolated backend tests using temporary databases and uploads.

## Verification

Backend tests: 145 passed
Frontend production build successful
Manual browser testing completed
Single-document conversations verified
Multi-document conversations verified
Follow-up questions verified
Hallucination prevention regression tested
Repeated backend test runs verified
Filename references verified

## Result

LearnFlow now supports natural conversational retrieval while preserving grounded Retrieval-Augmented Generation. Follow-up questions retrieve the correct document context without weakening hallucination prevention, multi-document chat remains fully supported, and the testing infrastructure is now isolated and repeatable.



# V2.1 — Workspace Polish

## Goal:

Transform LearnFlow into a polished AI study workspace by improving layout, navigation, scrolling behavior, and overall usability without changing the backend architecture.

## Features Completed

Redesigned three-panel workspace
Improved visual spacing and hierarchy
Guided empty workspace
Upload action moved to top of library
Sticky AI chat composer
Independent chat scrolling
Automatic single-document chat synchronization
Improved multi-document workflow
Scroll-to-latest button
Lightweight Markdown rendering
Browser page scroll prevention
Responsive flex layout fixes
Search input overflow fixes

## Learned

Flexbox layout architecture
Scroll container design
React layout composition
UX trade-offs for AI applications
Derived state vs duplicated state

## Problems Faced

Browser page jumped during chat updates
Chat context could drift from the selected document
Nested flex layouts caused overflow bugs
Sidebar search controls clipped on narrower widths

## Solutions

Isolated scrolling to the chat container
Introduced automatic document-chat synchronization
Reworked flex layout with flex-1 and min-h-0
Simplified responsive layouts to avoid clipping

## Verification

Backend tests: 145 passed
Frontend production build successful
Manual browser testing completed
Independent scrolling verified
Multi-document chat verified
Automatic document synchronization verified
Browser page scroll prevention verified
Existing V2 regression testing completed

## Result

LearnFlow now provides a significantly more polished and intuitive study workspace. Navigation is smoother, chat remains synchronized with the active document, scrolling behaves predictably, and the overall experience better supports extended study sessions.


# V2.1 — Milestone 2

## Goal

Implement workspace session persistence so users can seamlessly continue studying after refreshing the page or switching between documents.

## Features Completed

- Workspace session persistence
- Automatic workspace restoration
- Per-document conversation history
- Multi-document conversation persistence
- New Conversation action
- Persistent study tab selection
- Persistent document selection
- Search persistence
- Sort persistence
- Library scroll position restoration
- Centralized persistence utility

## Learned

- Browser localStorage architecture
- Persisting React application state
- Separating UI state from backend state
- Designing reusable persistence utilities
- Stable key generation using document IDs

## Problems Faced

- Restoring workspace state without race conditions
- Preserving conversations across document renames
- Managing separate conversations for different document combinations
- Preventing persistence logic from being scattered across components

## Solutions

- Introduced a centralized persistence utility
- Stored conversations using document IDs instead of filenames
- Generated multi-document keys using sorted document IDs
- Persisted only meaningful workspace state while excluding temporary UI state

## Verification

- Backend tests: **145 passed**
- Frontend production build successful
- Manual browser testing completed
- Workspace restoration verified
- Per-document conversations verified
- Multi-document conversations verified
- New Conversation verified
- Search persistence verified
- Sort persistence verified
- Library scroll restoration verified
- Rename regression verified
- Existing V2 regression testing completed

## Result

LearnFlow now preserves the user's entire study workspace across page refreshes and browser restarts. Documents, conversations, study tabs, search state, sorting preferences, and workspace context are restored automatically, creating a significantly smoother and more professional learning experience.