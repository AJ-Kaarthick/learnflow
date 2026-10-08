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

# V2.1 — Milestone 3

## Goal

Allow users to personalize the workspace while improving accessibility and visual consistency without changing application architecture.

## Features Completed

- Theme customization
- Light / Dark / System themes
- Accent color themes
- Comfortable and Compact density modes
- Persistent appearance settings
- Settings panel
- Accessibility improvements
- Reduced motion support
- Final UI polish

## Learned

- CSS variable based theming
- Theme persistence
- Accessibility fundamentals
- Centralized UI state management
- Designing scalable design systems

## Problems Faced

- Supporting multiple themes without duplicating styles
- Preventing flash of incorrect theme during page load
- Maintaining accessibility while adding customization

## Solutions

- Introduced centralized personalization context
- Built CSS-variable driven theming
- Persisted appearance preferences
- Added accessibility improvements throughout the workspace

## Verification

- Backend tests: **145 passed**
- Frontend production build successful
- Manual browser testing completed
- Theme switching verified
- Appearance persistence verified
- Accessibility verified
- Existing feature regression testing completed

## Result

LearnFlow now provides a fully customizable study workspace. Users can personalize appearance while maintaining accessibility, consistency, and persistent preferences across sessions.


# V2.1 — Milestone 4

## Goal

Improve productivity and chat usability through keyboard shortcuts, richer message rendering, reusable UI components, and workflow enhancements without changing the backend architecture.

## Features Completed

- GitHub-flavored Markdown rendering
- Keyboard shortcuts
- Keyboard shortcuts dialog
- Shared modal component
- Copy AI responses
- Regenerate responses
- Stop generation
- Chat timestamps
- Improved source viewer
- Improved loading indicators

## Learned

- Markdown rendering in React
- Keyboard accessibility
- Reusable modal architecture
- AbortController for request cancellation
- Component composition

## Problems Faced

- Rendering Markdown consistently
- Preventing shortcut conflicts while typing
- Supporting cancellation of in-flight requests

## Solutions

- Added react-markdown with remark-gfm
- Scoped global shortcuts appropriately
- Added AbortController support
- Centralized modal behavior

## Verification

- Backend tests: **145 passed**
- Frontend production build successful
- Manual browser testing completed
- Keyboard shortcuts verified
- Markdown rendering verified
- Stop generation verified
- Existing feature regression testing completed

## Result

LearnFlow now provides a more productive and polished study experience through richer chat rendering, keyboard-driven workflows, reusable UI infrastructure, and improved interaction feedback.


# V2.2 — Milestone 1

## Goal

Extend LearnFlow beyond PDFs by introducing DOCX support while preserving the existing Retrieval-Augmented Generation architecture.

## Features Completed

- DOCX upload support
- Generic document extraction service
- DOCX text extraction
- Shared extraction pipeline
- Mixed PDF + DOCX multi-document chat
- Generic upload validation
- Generic storage workflow
- Compact document library redesign
- Simplified workspace header
- UI polish

## Learned

- Word document structure
- Generic document processing pipelines
- Designing format-independent architectures
- Reusing RAG across multiple document types

## Problems Faced

- DOCX has no reliable page-count metadata.
- Needed to preserve reading order across paragraphs and tables.
- Existing upload pipeline assumed PDF-specific services.

## Solutions

- Introduced a document extraction abstraction.
- Implemented DOCX extraction using python-docx.
- Made upload/storage workflows format-agnostic.
- Displayed page count only when available.

## Verification

- Backend tests: **169 passed**
- Frontend production build successful
- Manual browser testing completed
- PDF upload verified
- DOCX upload verified
- Mixed PDF + DOCX chat verified
- Existing regression testing completed

## Result

LearnFlow now supports both PDF and DOCX documents while reusing the same Retrieval-Augmented Generation pipeline, allowing every AI feature to operate on multiple document formats without architectural changes.


# V2.2 — Milestone 2

## Goal

Extend LearnFlow's generic document pipeline to support PowerPoint presentations while preserving the existing Retrieval-Augmented Generation architecture.

## Features Completed

- PPTX upload support
- PPTX text extraction
- Generic presentation extraction
- Shared document extraction pipeline
- Mixed PDF + DOCX + PPTX multi-document chat
- Generic upload validation
- Backend tests

## Learned

- PPTX document structure
- Presentation text extraction
- Reusing format-independent architectures
- Generic document processing

## Problems Faced

- Slides contain many different shape types.
- PPTX has no reliable page-count metadata.
- Needed to preserve slide reading order.

## Solutions

- Added pptx_service.py.
- Extended the document extraction dispatcher.
- Reused the generic upload and RAG pipelines.

## Verification

- Backend tests: **195 passed**
- Frontend production build successful
- Manual browser testing completed
- PPTX upload verified
- Mixed-format chat verified
- Regression testing completed

## Result

LearnFlow now supports PDF, DOCX, and PPTX documents through a single reusable extraction pipeline while preserving the existing Retrieval-Augmented Generation architecture.


# V2.2 — Milestone 3

## Goal

Improve multi-document retrieval quality through adaptive retrieval, better ranking, comparison-aware prompting, and smarter evidence selection.

## Features Completed

Adaptive retrieval budget
Balanced retrieval
Duplicate chunk removal
Comparison-aware prompting
Informative retrieval failures
Mixed-format retrieval improvements
Backend tests

## Learned

Retrieval ranking
Context budgeting
Prompt specialization
Multi-document reasoning

## Problems Faced

Fixed retrieval budgets did not scale well.
Duplicate chunks wasted valuable context.
Comparison questions required different prompting.
Generic "not found" responses provided little insight.

## Solutions

Adaptive retrieval budgets based on document count.
Duplicate chunk filtering while preserving each document's strongest evidence.
Comparison-aware prompt construction.
More informative retrieval failures.

## Verification

Backend tests: 211 passed
Frontend production build successful
Manual browser testing completed
Multi-document summarization verified
Multi-document comparison verified
Mixed-format retrieval verified
Regression testing completed

## Result

LearnFlow now performs significantly stronger multi-document retrieval through adaptive evidence selection, better ranking, and comparison-aware prompting while preserving the existing Retrieval-Augmented Generation architecture.


## V2.3 — Milestone 1: OCR Support

Added OCR support for image documents and scanned PDFs.

The OCR pipeline integrates with the existing generic document extraction flow so OCR-extracted text can continue through chunking, embeddings, retrieval, summaries, flashcards, quizzes, mind maps, and chat without format-specific changes to those features.

OCR processing requires system-level `tesseract` and Poppler dependencies. Because these dependencies cannot be installed through Python requirements alone, LearnFlow now checks for them during application startup and logs actionable warnings when they are unavailable.

Document extraction failures are also logged with the underlying exception, document filename, and document id instead of silently transitioning the document to a failed state.

Tests cover OCR dependency detection, extraction failure logging, and regression behavior for existing document formats.

Verification:
- Backend: 260 tests passed
- Frontend production build succeeded



## V2.3 — Milestone 1: Generated Content Persistence Fix

Fixed an issue where generated summaries, flashcards, quizzes, or mind maps could disappear when switching between study tabs before refreshing the page.

Study panels are unmounted when switching tabs, while their generated content was previously held only in local component state. Generated results are now propagated back to the shared workspace cache so remounted panels receive the latest generated content.

This preserves the existing backend caching behavior and does not introduce a separate caching mechanism.

Added dependency-free frontend regression tests using Node's built-in test runner.

Verification:
- Frontend tests: 6 passed
- Backend tests: 260 passed
- Frontend production build succeeded

# V2.4 — Milestone 1: Chat UX Polish

## Goal

Improve the reliability and usability of document-based AI features, particularly when documents contain little or no readable text, while improving the multi-document Chat experience.

## Features Completed

- Document readability validation before AI generation
- Prevented Summary, Flashcards, Quiz, and Mind Map generation for documents with no readable text
- Shared no-readable-text UI state
- Improved warning/error readability and dark-mode contrast
- Readability-aware multi-document Chat
- Unreadable document identification by filename
- Prevented unreadable documents from blocking readable documents in mixed selections
- Preserved single- and multi-document Chat behavior
- Automatic Chat document-library refresh after upload
- Frontend regression tests for document readiness and Chat document handling

## Problems Faced

- AI generation was being attempted even when extracted document text was empty.
- Empty prompts could produce plausible but unrelated AI-generated content.
- An unreadable document could previously cause a mixed-document Chat request to fail for all selected documents.
- Chat's document selection state did not initially preserve the document metadata required for readability detection.
- The Chat document library could remain stale after uploading a new document from Chat.

## Solutions

- Added document-readiness guards before AI generation.
- Added a shared frontend no-readable-text state.
- Filtered unreadable documents before multi-document Chat requests while explicitly identifying them to the user.
- Preserved document readiness metadata through Chat document-selection state.
- Reused the existing document-library refresh mechanism so Chat refreshes its library after upload.
- Added regression tests covering the affected data flows.

## Verification

- Backend tests: 281 passed
- Frontend tests: 42 passed
- Frontend production build successful
- Manual testing completed
- Readable document + unreadable document combination verified
- Unreadable document identification verified
- Chat document-library refresh after upload verified
- Existing single- and multi-document Chat behavior verified

## Result

LearnFlow now prevents document-based AI features from generating misleading content when no readable document text is available. Mixed readable/unreadable document selections are handled gracefully, and the Chat document library stays synchronized after uploads.


## V2.4 — Milestone 2

### Phase 1 — Backend Conversation Foundation

Implemented the backend foundation for persistent conversations.

#### Added

- Conversation model
- Message model
- ConversationDocument association model
- Conversation request/response schemas
- Conversation CRUD API
- Conversation document-association API
- Explicit cleanup of conversation-document associations when a document is deleted

#### API

- `POST /conversations`
- `GET /conversations`
- `GET /conversations/{id}`
- `PATCH /conversations/{id}`
- `DELETE /conversations/{id}`
- `PUT /conversations/{id}/documents`

#### Design

- Conversations and messages are now persisted in SQLite.
- Documents are associated with conversations through a dedicated join table.
- Existing `Document` model remains unchanged.
- Conversation deletion explicitly removes its messages and document associations.
- Document deletion explicitly removes its conversation associations.
- Existing document-scoped chat endpoints remain unchanged.

#### Verification

- Backend tests: 306 passed
- New conversation tests: 25
- OpenAPI routes verified
- No frontend changes in this phase

This phase establishes the backend persistence layer required for the upcoming persistent conversation workflow.


## V2.4 — Persistent Conversation Backend

### Milestone 2 — Conversation System

#### Phase 1 — Backend Conversation Foundation

- Added persistent Conversation model
- Added persistent Message model
- Added ConversationDocument association table
- Added conversation CRUD endpoints
- Added document-association management
- Added explicit cleanup when conversations or documents are deleted
- Added backend regression tests

#### Phase 2 — Persistent Message Handling

- Added conversation-aware message endpoint
- Persisted user and assistant messages
- Connected persistent conversations to the existing RAG pipeline
- Reused existing history-aware retrieval and multi-document retrieval
- Persisted source references and grounding metadata
- Added transaction-safe message persistence
- Added conversation activity tracking
- Added regression tests for conversation message handling

### Verification

- Backend test suite: 322 passed
- Existing RAG/chat tests remain passing
- Conversation message persistence verified through dedicated tests
- No frontend changes were made during these phases

---

## V2.4 — Milestone 2
### Phase 3 — Frontend Conversation Management and Reliability Fixes


## Goal

Complete the frontend layer for persistent conversations and resolve
reliability issues discovered during integration testing.

## Features Completed

- Added frontend conversation API integration
- Added conversation list and switching
- Added New Conversation workflow
- Added conversation deletion
- Added active-conversation fallback after deletion
- Added conversation rename support
- Restored persistent conversation messages from the backend
- Preserved conversation history across page refreshes
- Added conversation timestamp handling
- Preserved Chat history when selected documents are unreadable
- Fixed Chat uploads replacing existing document selections
- Preserved multi-document selection when adding new documents
- Added frontend regression tests for conversation lifecycle and document selection

## Problems Faced

- SQLite datetime values could lose timezone information during serialization,
  causing newly created conversations to appear several hours old in the UI.
- When all selected documents were unreadable, the Chat error state replaced
  the entire message history instead of displaying the history alongside the
  warning.
- Uploading a document from Chat could replace the existing document selection
  instead of merging the new document into it.
- The frontend had no conversation deletion workflow even though the backend
  API was already implemented.

## Solutions

- Added timezone-aware datetime normalization before API serialization.
- Updated Chat rendering so unreadable-document warnings do not hide existing
  conversation history.
- Changed Chat upload synchronization to merge newly uploaded documents with
  the existing selection.
- Added frontend conversation deletion and state-management logic.
- Reused the existing conversation creation workflow when the final active
  conversation is deleted.
- Added regression tests for the affected behaviors.

## Verification

- Backend tests: **326 passed**
- Frontend tests: **84 passed**
- Frontend production build successful
- Conversation deletion manually verified
- New Conversation workflow manually verified
- Conversation switching manually verified
- Conversation history restoration manually verified
- Conversation timestamps verified
- Unreadable-document Chat history behavior verified
- Chat document upload/selection synchronization verified
- Existing single-document Chat behavior preserved
- Existing multi-document Chat behavior preserved
- Existing feature regression testing completed

## Result

LearnFlow now provides a complete frontend workflow for persistent
conversations while preserving the existing grounded Chat architecture.

Users can create, switch, rename, and delete conversations, restore their
conversation history, and continue working with selected documents across
sessions. Reliability issues involving timestamps, unreadable documents, and
Chat document uploads were also resolved.


---

## V2.4 — Milestone 2

### Phase 4 — AI Conversation Titles

## Goal

Add automatic, semantic conversation titles while preserving manual conversation
renaming and the existing persistent Chat workflow.

## Features Completed

- Added AI-generated conversation titles
- Generated titles from the first meaningful user message
- Added selected document filenames as contextual information for title generation
- Added semantic title generation instead of raw filename concatenation
- Added multi-document comparison-aware title generation
- Preserved manually renamed conversation titles
- Limited automatic generation to the initial conversation title
- Returned the generated title with the message response for immediate frontend
  sidebar updates
- Added graceful title-generation failure handling
- Added backend regression tests for title generation and naming behavior

## Problems Faced

- Initial automatic titles could be overly generic when generated only from the
  user's first prompt.
- Document filenames were available during Chat processing but were not initially
  provided to the title-generation service.
- Multi-document conversations required document context without forcing every
  selected document into the generated title.

## Solutions

- Made the user prompt the primary signal for semantic title generation.
- Passed selected document filenames to the title-generation service as contextual
  information.
- Added explicit title-generation rules so document names provide context rather
  than being mechanically concatenated.
- Added protection against automatic titles overwriting manually renamed
  conversations.
- Kept title generation best-effort so failures do not break Chat.

## Verification

- Backend naming tests: **34 passed**
- Full backend test suite: **366 passed**
- Frontend tests: **90 passed**
- Frontend production build successful
- Semantic title generation manually verified
- Document-context title generation manually verified
- Multi-document comparison title generation manually verified
- Manual rename protection verified
- Conversation title persistence across refresh verified
- Initial-title-only behavior verified

## Result

LearnFlow now generates concise, semantic conversation titles that reflect the
user's conversation intent while using selected document context when helpful.
Multi-document comparisons receive meaningful comparison-oriented titles, while
manual conversation renames remain protected from automatic replacement.


---

## V2.4 — Milestone 2

### Phase 5 — Dynamic Document Context

## Goal

Allow document context to be added or removed from an existing conversation
without losing the conversation's persisted message history.

## Features Completed

- Added dynamic document context management for conversations
- Added support for adding documents to an existing conversation
- Added support for removing documents from an existing conversation
- Persisted conversation-document associations
- Preserved conversation history while changing document context
- Preserved existing document selection when uploading additional documents
- Prevented duplicate document selections
- Preserved unreadable-document handling
- Added regression coverage for dynamic document context behavior

## Problems Faced

- Document selection needed to change without resetting the active conversation.
- Adding a newly uploaded document could previously replace the existing Chat
  selection.
- Changing document context needed to preserve the existing conversation history.

## Solutions

- Used the existing conversation-document association to persist document context.
- Updated document selection without creating or replacing the conversation.
- Merged newly uploaded documents into the current Chat selection.
- Preserved the existing conversation messages when document context changes.
- Added regression tests for document-selection and persistence behavior.

## Verification

- Backend regression tests passed
- Frontend regression tests passed
- Frontend production build successful
- Documents could be added to an existing conversation
- Documents could be removed from an existing conversation
- Conversation history remained intact after document-context changes
- Additional Chat uploads merged with the existing selection
- Duplicate document selection was prevented
- Unreadable-document handling remained intact

## Result

LearnFlow now supports dynamic document context within persistent conversations.
Users can add or remove documents from an existing conversation while preserving
the conversation history and without creating a new conversation.

---

## V2.4 — Milestone 2

### Phase 6 — localStorage Migration

## Goal

Complete the migration from legacy conversation-specific localStorage state to
the server-backed conversation system while preserving unrelated workspace
persistence.

## Features Completed

- Verified that conversation messages are no longer stored in localStorage
- Verified that per-conversation document state is no longer stored in localStorage
- Verified that multi-document conversation state is no longer stored in localStorage
- Retained only the active conversation ID as a minimal UI restoration pointer
- Preserved unrelated workspace localStorage persistence
- Added regression tests preventing reintroduction of legacy conversation caches

## Problems Faced

- The original V2 architecture stored conversation state locally in the browser.
- After server-backed conversations were introduced, the remaining localStorage
  usage needed to be distinguished from obsolete conversation caching.
- Removing legitimate workspace persistence could have caused unrelated
  functionality to regress.

## Solutions

- Audited frontend localStorage and sessionStorage usage.
- Confirmed that conversation messages, document context, and multi-document
  conversation state are sourced from the server-backed conversation system.
- Retained only the active conversation ID as a minimal client-side UI pointer.
- Preserved unrelated workspace persistence such as document, study, library,
  and appearance state.
- Added regression tests to prevent legacy conversation caches from returning.

## Verification

- Backend tests: 366 passed
- Frontend tests: 93 passed
- Frontend production build successful
- Conversation history restoration verified
- Conversation switching verified
- Conversation document context verified
- Dynamic document add/remove behavior preserved
- Legacy conversation localStorage caches confirmed absent
- Unrelated localStorage persistence preserved

## Result

LearnFlow now uses the server-backed conversation system as the source of truth
for persistent conversation state. Legacy conversation message and document
caches have been removed, while the minimal active conversation ID remains as a
client-side UI restoration pointer.

---

## V2.4 — Milestone 2

### Phase 7 — Polish / Regression

## Goal

Perform a final regression and polish pass across the V2.4 persistent
conversation system and verify that the completed phases work together
correctly.

## Features Completed

- Final regression review of the V2.4 conversation workflow
- Verified conversation creation, switching, deletion, and rename behavior
- Verified AI-generated title behavior and manual rename protection
- Verified dynamic document add/remove behavior
- Verified Chat document upload synchronization
- Verified server-backed conversation persistence
- Added regression coverage for removed-document RAG context
- Confirmed legacy conversation localStorage caching remains absent

## Problems Faced

- No production regression was identified during the final review.
- One remaining test-coverage gap was found around document removal during
  an existing conversation.

## Solutions

- Added a focused regression test covering document removal from a
  conversation.
- The test verifies that a removed document is excluded from subsequent
  RAG context while previously persisted conversation history remains intact.
- No production code changes were required.

## Verification

- Backend tests: **367 passed**
- Frontend tests: **93 passed**
- Frontend production build successful
- Final conversation lifecycle regression review completed
- Dynamic document-context behavior verified
- Removed-document RAG behavior verified
- Legacy conversation localStorage caches confirmed absent

## Result

V2.4 Milestone 2 is now complete. LearnFlow uses the server-backed
conversation system as the source of truth for persistent conversation
state, supports dynamic document context and semantic AI conversation
titles, and has completed the final regression pass.

---

# V3 — Milestone 1: Authentication & Guest Access

## Phase 1 — Guest Identity & Session Foundation

### Goal

Introduce the identity foundation required for V3 guest access and
authenticated user support while preserving the existing V2.4 application
behavior.

### Features Completed

- Added guest identity support
- Added temporary guest session management
- Added guest session cookie
- Added credentialed frontend API requests
- Added backend identity resolution
- Added `/api/v1/identity/me` endpoint
- Preserved guest identity across page refreshes
- Isolated guest identities between separate browser sessions
- Added guest session expiration handling
- Preserved existing document and conversation API behavior

### Architecture

V3 introduces an identity layer that distinguishes temporary guest sessions
from future persistent user accounts.

Guest sessions provide a temporary identity without requiring authentication.
The identity is established through the guest session and resolved by the
backend for API requests.

The identity layer will become the foundation for authenticated accounts,
user ownership, data isolation, and guest-to-account migration in later
phases.

### Problems Faced

- Introducing credentialed API requests without breaking existing API usage
- Establishing a stable guest identity across page refreshes
- Ensuring separate browser sessions receive separate guest identities
- Defining a real expiration boundary for temporary guest sessions

### Solutions

- Centralized API requests through the existing frontend API layer
- Added guest-session credentials to API requests
- Added backend identity resolution
- Used a browser cookie to maintain the active guest session
- Added expiration handling for guest sessions
- Verified identity isolation using separate browser sessions

### Verification

- Backend tests: **383 passed**
- Frontend tests: **93 passed**
- Frontend production build successful
- Guest session cookie verified in browser storage
- Guest session persistence across refresh verified
- Guest identity resolution verified through `/api/v1/identity/me`
- Separate guest identities verified using Firefox and Brave
- Existing `/documents` API request returned `200 OK`
- Backend `/health` endpoint verified
- No document/RAG regression testing was required because the document/RAG
  implementation was not modified in this phase

### Result

LearnFlow now has the initial V3 identity foundation required for guest-first
access. Users can receive a temporary guest identity without signing in,
while the existing V2.4 document, Chat, and RAG functionality remains
available through the centralized API layer.

This phase establishes the identity boundary required for subsequent
authentication, account ownership, and guest-to-account migration work.

---

# V3 — Milestone 1: Authentication & Guest Access

## Phase 2 — Sign Up / Sign In & Credential Validation

### Goal

Introduce persistent user authentication while preserving the V3 guest
identity foundation and existing application behavior.

### Features Completed

- Added user sign-up
- Added user sign-in
- Added email validation
- Added password validation and policy enforcement
- Added credential verification
- Added invalid-credential error handling
- Added authenticated session establishment
- Added authenticated identity resolution
- Added sign-out support
- Preserved the existing guest identity foundation
- Added backend and frontend authentication test coverage

### Architecture

Phase 2 builds authenticated user accounts on top of the V3 identity layer
introduced in Phase 1.

The system now distinguishes between temporary guest identities and
authenticated user identities.

Authentication requests are handled through the centralized frontend API
layer and resolved by the backend. Credential validation and authentication
state remain backend responsibilities.

Guest sessions continue to function independently, while authenticated users
receive a persistent account identity that will become the ownership boundary
for later V3 milestones.

### Problems Faced

- Validating authentication credentials consistently
- Providing clear errors for invalid credentials
- Enforcing email and password validation rules
- Preserving the existing guest identity behavior while introducing accounts
- Keeping authentication logic behind the existing API architecture

### Solutions

- Added centralized authentication API handling
- Added backend credential validation
- Added email and password validation
- Added authenticated session handling
- Preserved the existing guest-session identity mechanism
- Added regression coverage for authentication behavior
- Verified invalid and valid credential flows independently

### Verification

- Backend tests: **427 passed**
- Frontend tests: **133 passed**
- Frontend production build successful
- Sign-up flow verified
- Sign-in flow verified
- Email validation verified
- Password validation verified
- Invalid credentials correctly rejected
- Valid credentials correctly accepted
- Authenticated session establishment verified
- Existing guest identity behavior preserved

### Result

LearnFlow now supports both temporary guest identities and authenticated
user accounts. Users can create accounts and sign in using validated
credentials while the existing guest-first identity foundation remains intact.

This phase establishes the authentication layer required for subsequent
session management, guest-to-account migration, user ownership, and protected
persistent data.

---

# V3 — Milestone 1: Authentication & Guest Access

## Phase 3 — Guest Limits + Guest→Account Migration

### Goal

Complete the V3 guest-first identity flow by adding backend-enforced guest
usage limits, guest-to-account migration, and ownership-based data isolation
while preserving the existing V2.4 behavior and authentication foundation.

### Features Completed

- Added server-enforced guest usage limits
- Added guest usage tracking by guest session
- Added guest-to-account data migration
- Added transaction-safe guest migration
- Added guest-session expiration enforcement
- Added ownership-aware documents
- Added ownership-aware conversations
- Added backend-enforced user data isolation
- Preserved authenticated user access to owned persistent data
- Preserved guest identity and authentication behavior
- Added password confirmation validation
- Added password visibility controls
- Added frontend regression coverage for authentication UX

### Architecture

Phase 3 completes the ownership boundary introduced by the V3 identity layer.

Guest-owned documents and conversations are associated with the active guest
session, while authenticated data is associated with the authenticated user.

Guest usage limits are enforced by the backend and tracked against the guest
session, preventing frontend state changes or page refreshes from bypassing
the configured limits.

When a guest creates an account while the guest session remains active,
eligible guest-owned documents and conversations are migrated to the newly
created user account.

Migration is performed transactionally and is restricted to the active guest
session. Data belonging to other guest sessions or authenticated users is not
included.

After migration, the authenticated user becomes the owner of the migrated
data and backend authorization prevents unrelated users from accessing it.

### Problems Faced

- Existing local SQLite databases used the pre-Phase-3 schema and did not
  contain the new ownership fields.
- Guest limits needed to remain effective across refreshes and frontend state
  changes.
- Guest-to-account migration needed to avoid accidentally migrating unrelated
  data.
- Ownership needed to be enforced by the backend rather than trusted from
  frontend state.
- Password confirmation and visibility needed to be added without changing
  the existing authentication architecture.

### Solutions

- Verified the Phase 3 ownership schema using a fresh SQLite database.
- Added backend-enforced guest usage accounting.
- Scoped guest migration to the active guest session.
- Performed migration transactionally.
- Added backend ownership checks for protected persistent data.
- Preserved the existing guest identity and authenticated session mechanisms.
- Added password confirmation validation and password visibility controls.
- Added frontend regression coverage for the authentication UI changes.

### Database Compatibility Note

Phase 3 requires the updated ownership-aware database schema.

A fresh database created from the current Phase 3 schema is supported.

Existing SQLite databases created under the pre-Phase-3 schema are not
automatically migrated. The existing database migration strategy is deferred
to V3 Milestone 2, which will establish the long-term database architecture,
PostgreSQL transition, and migration strategy.

### Verification

- Backend tests: **464 passed**
- Frontend tests: **159 passed**
- Production build successful
- Guest identity and session behavior verified
- Guest upload limit verified
- Guest session persistence across refresh verified
- Guest → account migration verified
- Account logout/login persistence verified
- Cross-account data isolation verified
- Separate account does not see another account's documents
- Password confirmation validation verified
- Password visibility controls verified

### Result

V3 Milestone 1 now provides the complete guest-first authentication and
ownership foundation required for subsequent V3 work.

LearnFlow supports temporary guest identities, authenticated user accounts,
backend-enforced guest limits, guest-to-account migration, and ownership-based
data isolation.

The milestone establishes the identity and ownership boundary required for
the V3 database architecture, study, revision, progress, dashboard, and
sharing features.

---

# V3 — Milestone 2: Database & User Data Architecture

## Phase 1 — Database Architecture & Migration Foundation

### Goal

Establish the long-term database migration and schema-management foundation
required for the V3 user-data architecture while preserving existing LearnFlow
behavior and preparing the project for the SQLite → PostgreSQL migration.

### Features Completed

- Added Alembic as the authoritative database migration framework
- Added the current V3 schema to migration history
- Added fresh database initialization through Alembic
- Added dialect-aware database engine configuration
- Added PostgreSQL compatibility
- Added timezone-aware database timestamps
- Added legacy SQLite schema drift detection
- Prevented incompatible legacy databases from being falsely stamped as current
- Preserved existing legacy database data
- Added migration regression coverage
- Added PostgreSQL compatibility testing

### Architecture

Alembic is now the authoritative mechanism for database schema evolution.

Fresh databases are initialized through the migration history.

Already-managed databases use normal Alembic upgrade behavior.

Legacy databases are inspected before migration state is established. A legacy
database whose schema genuinely matches the current schema may be adopted at
the current migration head.

An incompatible legacy database is not falsely stamped as current. Schema drift
is reported and the existing database remains untouched.

The application therefore does not silently claim that an incompatible legacy
database matches the current schema.

SQLite and PostgreSQL use the same environment-driven database configuration,
with dialect-specific engine behavior where required.

### Problems Faced

- Existing V2.4 SQLite databases predated the V3 ownership schema.
- SQLAlchemy's previous startup schema creation approach could not safely evolve
  existing tables.
- Blindly stamping an incompatible legacy database would incorrectly mark it as
  current.
- SQLite-specific engine configuration was not suitable for PostgreSQL.
- Database timestamp behavior needed to remain compatible across database
  dialects.

### Solutions

- Introduced Alembic for authoritative schema migrations.
- Added a genesis migration representing the current V3 schema.
- Added safe migration/bootstrap handling for fresh, managed, and legacy
  databases.
- Added schema drift detection before legacy database adoption.
- Preserved incompatible legacy databases without destructive changes.
- Added dialect-aware SQLAlchemy engine configuration.
- Updated database timestamps to use timezone-aware types.
- Added SQLite and PostgreSQL regression coverage.

### Database Compatibility Note

Existing SQLite databases created under the pre-Phase-3 schema are not
automatically migrated.

This is intentional.

M2 Phase 1 establishes the migration infrastructure and schema-management
foundation. The actual SQLite → PostgreSQL data migration and legacy schema/data
reconciliation are deferred to M2 Phase 2.

An incompatible legacy database is therefore expected to require the Phase 2
migration work before it can be used with the complete ownership-aware schema.

### Verification

- Backend tests: **479 passed, 1 skipped** without PostgreSQL
- Backend tests: **482 passed, 0 skipped** with PostgreSQL 16
- Frontend tests: **159 passed**
- Production build successful
- Fresh SQLite migration verified
- Legacy schema drift detection verified
- Incompatible legacy database not falsely stamped
- Legacy data preservation verified
- PostgreSQL compatibility verified against a live PostgreSQL 16 instance
- Real FastAPI application boot verified against a simulated legacy database

### Result

V3 Milestone 2 now has a reliable database migration foundation.

LearnFlow can initialize the current schema through Alembic, operate with
SQLite or PostgreSQL-compatible database configuration, detect incompatible
legacy schemas, and preserve legacy data without falsely claiming that the
database is already current.

The actual SQLite → PostgreSQL data migration and legacy data reconciliation
remain the responsibility of V3 Milestone 2, Phase 2.

## Phase 2 — SQLite → PostgreSQL Data Migration & Legacy Schema Reconciliation

### Goal

Provide a safe, explicit, repeatable migration path from both legacy V2.4 SQLite and
modern V3 SQLite into PostgreSQL, reconciling legacy unowned learning records with the V3
ownership architecture, validating physical storage files, and ensuring transactional safety.

### Features Completed

- Implemented dedicated migration engine (`backend/app/db/sqlite_to_postgres.py`)
- Added migration CLI (`backend/app/db/cli.py`) with support for `--sqlite-path`,
  `--postgres-url`, `--target-user-email`, `--target-user-id`, `--source-storage-dir`,
  `--target-storage-dir`, and `--dry-run`
- Enforced read-only access to source SQLite databases
- Enforced target PostgreSQL pre-migration check against Alembic head
- Enforced mandatory target user identity for legacy V2.4 application data (`owner_type = "user"`,
  `owner_id = target_user.id`), rejecting NULL ownership
- Supported modern V3 SQLite migration while preserving existing valid user and guest ownership
- Added physical document file validation ensuring all referenced binaries exist in storage
- Added cross-storage physical file copying with cleanup on transaction failure
- Enforced atomic transaction boundary with full rollback on migration failure
- Added deterministic idempotency preventing duplicate records on rerun while catching conflicts
- Preserved all dependent learning data (summaries, flashcards, quiz questions, mind maps,
  chunks with embedding vectors, conversations, messages with grounding metadata, and associations)
- Added type normalization converting naive SQLite timestamps to UTC TIMESTAMPTZ, booleans, and JSON
- Added comprehensive automated test suite in `tests/test_sqlite_to_postgres.py`

### Architecture

The SQLite → PostgreSQL data migration is intentionally decoupled from web application startup.
Startup remains responsible for bootstrapping the active database, while data migration is an
explicit administrative operation executed through the CLI.

Legacy V2.4 was fundamentally single-user and local with no concept of accounts or guest sessions.
Therefore, migrating legacy application data strictly requires an explicit target user identity
resolved against the target database's `users` table.

Physical files in storage are treated as first-class components of the migration: database rows
are never migrated if their underlying physical files cannot be verified.

Target database writes execute in strict foreign-key dependency order within a single transaction,
guaranteeing clean rollback if any record or storage operation fails.

### Problems Faced

- Legacy V2.4 databases lacked ownership columns, which caused standard ORM queries to fail
  due to missing columns.
- SQLite drops timezone information from timestamps and stores booleans as integers.
- Vector embeddings and complex JSON structures stored in SQLite text fields required careful
  deserialization to avoid double-encoding in PostgreSQL.
- Filesystem file copies are not natively transactional with relational database commits.

### Solutions

- Used low-level inspection and raw mapping queries against the read-only SQLite database to
  extract records independently of model column presence.
- Implemented robust type normalization routines for datetimes, booleans, and JSON structures.
- Implemented physical file validation prior to transaction start and tracked newly copied files
  so they can be removed if the database transaction aborts.
- Enforced target user resolution, rejecting migrations where legacy application data lacks
  an owner.

### Verification

- Backend tests: **500 passed, 0 skipped** (with live PostgreSQL test suite enabled; **490 passed, 2 skipped** in standalone SQLite environments)
- Frontend tests: **159 passed, 0 failed**
- Legacy V2.4 schema detection and data migration verified
- Target user resolution (by id, by email, nonexistent, conflict, missing) verified
- Modern V3 SQLite migration with preserved ownership verified
- Type normalization across datetimes, booleans, JSON, and embeddings verified
- Missing physical file detection and safe cross-directory file copying verified
- Mid-transaction failure rollback and copied file cleanup verified
- Idempotent rerun and conflict detection verified
- Dry-run validation mode verified
- CLI execution verified

### Result

V3 Milestone 2 Phase 2 is complete. LearnFlow provides a robust, safe, and repeatable data
migration path from SQLite to PostgreSQL with legacy schema reconciliation and physical storage
synchronization.

## Phase 3 — Persistent Revision Data Model

### Goal

Establish the persistent revision data model foundation separating immutable question definitions
from learner attempts, enabling multi-document review sessions, enforcing top-level ownership
scoping, ensuring historical durability across document deletions, and supporting guest-to-account
ownership migration.

### Features Completed

- Implemented core SQLAlchemy revision models in `backend/app/db/models.py`:
  - `RevisionSession`: Root session aggregate with `owner_type`, `owner_id`, `title`, `session_type`,
    and `status`
  - `RevisionSessionDocument`: Composite primary key join table `(session_id, document_id)` enabling
    multi-document revision scoping
  - `RevisionQuestion`: Immutable question definition with prompt, answer key, options, explanation,
    position, difficulty, and frozen evidence provenance (`source_document_id`, `evidence_snippet`,
    `evidence_metadata`)
  - `RevisionAttempt`: Append-only learner attempt with `attempt_number`, answer, correctness, score,
    feedback, time spent, and submission timestamp
- Added clean, reversible Alembic migration `74eb271ec556_revision_data_model.py` chained from `505909c1ba21`
  with indexes and foreign key constraints
- Implemented `Question != Attempt` structural separation allowing multiple attempts per question over time
- Enforced top-level session ownership inheritance (`RevisionQuestion`, `RevisionAttempt`, and
  `RevisionSessionDocument` inherit ownership from `RevisionSession`)
- Decoupled document deletion: Deleting a document unlinks `RevisionSessionDocument` join rows and sets
  `RevisionQuestion.source_document_id = NULL` without deleting the session, questions, or attempts
- Preserved frozen evidence provenance: Questions maintain self-contained evidence snapshots
  (`evidence_snippet`, `evidence_metadata`) ensuring historical revision integrity even if source documents are deleted
- Integrated revision session transfer into `guest_migration_service.py` (`revision_sessions_migrated`)
- Maintained compatibility with both SQLite and PostgreSQL 16 (including `TIMESTAMPTZ` and indexed ownership)
- Preserved complete boundary separation: Did not touch Study Quiz behavior, and did not introduce premature
  Revision API routes, UI, generation services, or derived mastery/spaced repetition logic
- Added comprehensive automated test suite in `backend/tests/test_revision_models.py` (14 unit and integration
  tests), and extended `test_postgres_compatibility.py` and `test_migrations.py`

### Architecture & Boundaries

The revision domain separates raw historical learning evidence from derived intelligence:
- **Root Aggregate:** `RevisionSession` is the single owner-scoped root (`owner_type`, `owner_id`).
- **Composite Scoping:** `RevisionSessionDocument` enables sessions to span arbitrary sets of documents.
- **Immutable Questions vs Mutable Attempts:** Questions capture the prompt and evidence snapshot at generation time;
  attempts capture learner responses and evaluations at review time.
- **Document Deletion Resilience:** Historical review sessions and learner attempts survive source document deletion.
- **No Premature Intelligence:** Spaced repetition scheduling and mastery metrics are intentionally deferred to future
  milestones; Phase 3 strictly provides the durable relational foundation.

### Problems Faced

- In the test suite, dynamic migration bootstrapping occurs upon importing `app.main`. Ephemeral test databases
  need migration bootstrap to properly configure revision tables before running tests.
- Inserting duplicate composite PKs or unique constraint violations within the same SQLAlchemy session raised
  client-side identity map warnings (`SAWarning: New instance conflicts with persistent instance`).
- Ensuring `ondelete="SET NULL"` for `RevisionQuestion.source_document_id` works cleanly in both SQLite and
  PostgreSQL during active deletion workflows.

### Solutions

- Explicitly imported `app` from `app.main` in test files that spin up fresh database engines to ensure Alembic
  startup migrations run consistently.
- Executed constraint violation assertions across distinct session instances (`Session(bind)`) to test true
  database-level constraint enforcement.
- Updated `routes_documents.py` to explicitly remove join table records and nullify `source_document_id` on
  deletion, providing guaranteed cross-database durability.

### Verification

- Backend tests: **514 passed, 0 skipped, 0 failed** in 63.01s (with live PostgreSQL 16 instance enabled)
- Frontend tests: **159 passed, 0 failed**
- Alembic migration upgrade and downgrade verified
- Schema idempotency and clean single migration head verified
- Question vs Attempt separation and sequential attempt numbering verified
- Multi-document revision scoping verified
- Top-level ownership isolation and guest-to-user migration verified
- Source document deletion resilience with frozen evidence snapshots verified
- PostgreSQL 16 compatibility (`TIMESTAMPTZ`, index creation, ownership queries) verified

### Result

V3 Milestone 2 Phase 3 is complete. LearnFlow has a robust, durable, and ownership-aware revision data model
ready for integration and future revision milestone capabilities.

## Phase 4 — Integration, Isolation & Regression

### Goal

Complete V3 Milestone 2 by establishing full end-to-end integration and isolation guarantees across
guest sessions, user accounts, documents, conversations, and revision sessions; bridging modern V3
Revision tables in the SQLite → PostgreSQL data migration; and performing comprehensive regression
verification across both SQLite and live PostgreSQL 16.

### Features Completed

- Upgraded `sqlite_to_postgres.py` data migration tool to support modern V3 Revision tables:
  - Added extraction, dependency ordering, and conflict detection for `revision_sessions`,
    `revision_session_documents`, `revision_questions`, and `revision_attempts`
  - Normalized SQLite datetimes to timezone-aware UTC `TIMESTAMPTZ`
  - Normalized JSON fields (`config`, `options`, `evidence_metadata`) to valid Python dicts/lists for JSONB storage
  - Handled composite primary key uniqueness and duplicate skipping for `revision_session_documents`
  - Validated referential integrity across session, question, attempt, and document links
- Extended `backend/tests/test_sqlite_to_postgres.py`:
  - Added modern V3 revision data migration test asserting accurate target state, document join persistence,
    nullable `source_document_id`, frozen evidence preservation, and idempotent reruns
  - Added live PostgreSQL 16 integration test verifying modern V3 revision migration against real PostgreSQL
- Created dedicated integration test suite `backend/tests/test_m2_integration.py` covering:
  - `test_end_to_end_guest_to_account_lifecycle_with_revision`: Full HTTP and database lifecycle from anonymous
    guest document upload, conversation creation, and revision session creation through user signup, verifying
    atomic ownership transfer and guest session revocation
  - `test_multi_tenant_revision_data_isolation`: Scoped query isolation and ownership predicate checks preventing
    cross-tenant data leakage between users and guests
  - `test_multi_document_revision_partial_document_deletion`: Verified that deleting one document out of multiple
    in a revision session cleans up the document and join row, nullifies question `source_document_id`, and
    preserves frozen evidence snippets, metadata, the sister document, and historical attempt records
  - `test_conversation_revision_decoupled_lifecycle`: Verified mutual decoupling between Conversations and
    RevisionSessions sharing underlying documents across independent deletion events
- Extended `backend/tests/test_postgres_compatibility.py` with live PostgreSQL 16 tests:
  - `test_revision_document_deletion_durability_on_postgres`: Verified ON DELETE SET NULL foreign key behavior,
    JSONB metadata preservation, and session durability on live PostgreSQL
  - `test_revision_guest_to_account_migration_on_postgres`: Verified atomic revision session ownership transfer
    and guest revocation on live PostgreSQL
  - `test_revision_ownership_isolation_on_postgres`: Verified scoped query isolation between distinct users and
    guests on live PostgreSQL
- Maintained strict architectural boundaries: Did not introduce Revision Mode UI, API endpoints (`/revision/*`),
  AI generation, or spaced repetition/mastery intelligence. Preserved Study Quiz behavior without regressions.

### Problems Faced

- `sqlite_to_postgres.py` was implemented in Phase 2 prior to the introduction of Phase 3 Revision models and
  did not extract or insert revision tables.
- In SQLite, raw SQL mapping queries return JSON columns as text strings and booleans as integers (0/1),
  requiring defensive deserialization and type casting in assertion logic.
- Testing true database-level constraints on ephemeral SQLite test fixtures required distinct session bindings.

### Solutions

- Added modern V3 revision tables to `sqlite_to_postgres.py` extraction, validation, transformation, and
  insertion pipelines in foreign-key dependency order.
- Utilized robust JSON deserialization and boolean type normalization across migration and test assertions.
- Verified all durability, isolation, and migration workflows on both SQLite and live PostgreSQL 16.

### Verification

- Backend tests: **522 passed, 0 skipped, 0 failed** in 61.60s (with live PostgreSQL 16 instance enabled)
- Frontend tests: **159 passed, 0 failed** in 0.96s
- Single Alembic head `74eb271ec556` verified
- End-to-end guest-to-account lifecycle with revision assets verified
- Multi-tenant Revision data isolation verified
- Multi-document partial document deletion durability verified
- Conversation ↔ Revision domain decoupling verified
- SQLite → PostgreSQL modern V3 revision migration verified on SQLite and live PostgreSQL 16

### Result

V3 Milestone 2 is complete. LearnFlow has an integrated, multi-tenant, durable persistent database foundation
supporting users, guests, documents, conversations, and revision sessions across SQLite and PostgreSQL 16.

---

# V3 — Milestone 3: Study Experience 2.0

## Goal

Transform LearnFlow's Study workspace from a single-document utility into an intelligent, multi-document learning experience featuring top-down curriculum design (Learn Mode), conceptual relationship mapping (Visualize Mode), and grounded source citations across 1 to 10 study documents.

## Features Completed

### Phase 1 — Multi-Document Selection & Study Foundation
- Multi-document selection supporting 1 to 10 documents in the Study workspace
- Interactive document chip row with active focus, remove, and add document controls
- Document readiness classification (`readable`, `unreadable`, `processing`, `failed`)
- Explanatory advisory notices for mixed readiness without blocking readable documents
- Workspace persistence for `selectedStudyDocumentIds`, `activeDocumentId`, and `activeStudyTab`
- 100% backward compatibility for single-document study tools (Summary, Flashcards, Quiz, Mind Map)

### Phase 2 — Learn Mode Backend Foundation & RAG Grounding
- Curriculum outline endpoint (`POST /api/v1/study/learn/outline`) synthesizing coherent topics and subtopics
- Authoritative backend readiness and ownership partitioning returning explicit provenance metadata
- Topic deep-dive endpoint (`POST /api/v1/study/learn/topic`) with RAG vector search across selected document chunks
- Contextual learning actions (`explain`, `simplify`, `elaborate`, `example`)
- Pedagogical depth controls (`overview`, `standard`, `in-depth`)
- Grounded source citations, key terms definitions, and key takeaways
- Guest quota enforcement before generation and atomic accounting after success

### Phase 3 — Learn Mode Frontend Experience & Contextual Actions
- Positioned Learn as the primary first Study tab
- Dual-column curriculum layout with collapsible topic units, subtopics, and progress tracking
- Interactive topic viewer with Markdown rendering, key terms definitions, and key takeaways
- Contextual action bar enabling one-click simplification, deep dive, and concrete examples
- Pedagogical depth selector adjusting explanation detail on the fly
- In-memory ephemeral session caching preserving variations per topic without heavy localStorage bloat
- Stale curriculum detection prompting regeneration when study document selection changes

### Phase 4 — Visualize Mode & Concept Network Graph
- Positioned Visualize as the 6th Study tab alongside Mind Map
- Backend concept graph endpoint (`POST /api/v1/study/visualize/graph`) extracting concepts and semantic relationships
- Bounded graph complexity per depth: Overview (10 nodes/15 edges), Standard (16/26), In-depth (22/36)
- Interactive D3 force-directed canvas with pan, zoom, fit-to-view, and reset controls
- Concept node inspector displaying definitions, importance ratings, incident edges, and grounded chunk citations
- Category filtering and concept search
- Stale graph detection on selection changes

### Phase 5 — Final Integration, Regression, QA & Polish
- Dedicated cross-phase integration test suite (`backend/tests/test_m3_integration.py`) covering end-to-end guest lifecycle, mixed readiness, quota limits, and Revision isolation
- Standardized `AIProvider.generate_text` contract across all study features
- Resilient multi-strategy JSON parser in `extract_json` supporting conversational preambles and control characters
- Fallback grounding from raw document snippets when vector chunks are unavailable
- Clean Unicode rendering for JSX list markers, chevrons, and checkmark icons
- Decoupled Study tab strip from single-document readiness
- High-contrast semantic design tokens across Light/Dark modes and all 4 accent color themes

## Learned

- Context-window bounding: Distributing character budgets proportionally across up to 10 documents prevents LLM context overflow while ensuring balanced representation.
- Ephemeral vs. persistent state boundaries: Heavy AI-generated artifacts (curricula, graphs) are best kept in memory during active study sessions, avoiding localStorage quota overflow and stale cache bugs, while lightweight IDs and tab choices should be persisted.
- Resilient structured output extraction: LLMs occasionally produce markdown preambles or literal unescaped newlines in JSON strings; multi-strategy boundary extraction with `strict=False` parsing eliminates brittle 502 failures.
- Dual-mode workspace ergonomics: Decoupling multi-document synthesized modes (Learn, Visualize) from single-document focused modes (Summary, Flashcards, Quiz, Mind Map) allows users to explore cross-document insights without losing single-document precision.

## Problems Faced

- `visualize_service.py` called `ai_provider.generate_content`, which did not exist on `GeminiProvider`, causing 502 errors in production while masked in unit tests.
- Learn topic generation intermittently failed with 502 when LLMs included commentary outside code fences or unescaped newlines in markdown explanation fields.
- Non-standard XML entities (`&check;`, `&bull;`, `&rsaquo;`) rendered as literal strings in React JSX.
- Selecting an unready document in a multi-document selection unmounted the entire study tab bar.

## Solutions

- Aligned all services to the minimal `AIProvider.generate_text` contract and updated test mocks to enforce it.
- Upgraded `extract_json` to extract embedded code fences, isolate outermost JSON structures, and parse with `strict=False`.
- Replaced JSX HTML entities with inline SVG icons and explicit Unicode characters (`✓`, `•`, `›`).
- Updated `StudyWorkspace.jsx` so tabs and multi-doc panels render whenever readable documents exist, with focused advisories for unready single-document tools.

## Verification

- Backend tests: **558 passed, 5 skipped** in 66.28s
- Frontend tests: **221 passed, 0 failed** in 1.08s
- Production frontend build: successful with 0 errors
- Single Alembic head `74eb271ec556` verified
- Formatting check `git diff --check` clean
- Manual browser QA: verified across all themes, depths, contextual actions, and multi-document selections

## Result

V3 Milestone 3 is complete. LearnFlow provides an integrated, multi-document Study Experience 2.0 with curriculum-driven Learn Mode and interactive Visualize Mode knowledge graphs.

---

# V3 — Milestone 4: Revision Experience 2.0

## Goal

Build a dedicated, persistent learning evaluation system for active recall, practice, and test preparation across 1 to 10 documents, featuring grounded question generation (MCQ, open-ended, mixed), deterministic zero-quota MCQ scoring, rubric-guided AI evaluation for open-ended answers, immutable attempt history (`Question != Attempt`), session resume, and provenance citations.

## Features Completed

### Phase 1 — Revision Session Creation & Question Generation Backend
- Dedicated Revision REST API router (`POST /api/v1/revision/sessions`, `GET /api/v1/revision/sessions`, `GET /api/v1/revision/sessions/{id}`)
- Proportional character budgeting across 1 to 10 contributing documents (`max(1000, 30000 // len(documents))`)
- Grounded prompt construction and resilient JSON question extraction for `multiple_choice`, `open_ended`, and `mixed` modes
- Atomic persistence of `RevisionSession`, `RevisionSessionDocument`, and `RevisionQuestion` rows with strict user/guest ownership scoping
- Guest AI quota pre-check and post-generation accounting
- Comprehensive Phase 1 test suite (24 tests)

### Phase 2 — Answer Evaluation Engine & Attempt Tracking Backend
- Question attempt submission endpoint (`POST /api/v1/revision/sessions/{session_id}/questions/{question_id}/attempts`)
- Deterministic Python MCQ evaluator with case-insensitive option matching, letter prefixes ('A', 'B'), and zero AI quota consumption
- Rubric-guided AI evaluator for open-ended answers with structured JSON schema scoring (0.0–1.0) and constructive feedback
- Deterministic rejection for empty/trivial open-ended submissions (0 quota consumed)
- Immutable `RevisionAttempt` persistence with 1-indexed attempt numbers per question, leaving question prompts unaltered
- Authoritative session completion endpoint (`POST /api/v1/revision/sessions/{session_id}/complete`) calculating official score from latest attempts
- Comprehensive Phase 2 test suite (23 tests)

### Phase 3 — Frontend Revision Workspace & Active Session Runner
- Dedicated Revision top-level route and navigation bar link (`#/revision`)
- Interactive setup launcher supporting multi-document selection (1–10 documents), modes (`practice`, `quiz`, `flashcards`), difficulty, and question count
- Active session runner with keyboard shortcuts, timer, and question navigation dots
- Interactive MCQ option cards and open-ended textarea answer composer
- Immediate post-submission feedback cards displaying score, correct answer, explanation, and frozen evidence quotes
- Attempt retry mechanism with immutable history accumulation

### Phase 4 — Session History, Results Review, Resume & Multi-Document Polish
- Revision history list with session cards displaying score, completion badges, dates, and document chips
- In-progress session resume jumping directly to the first unattempted question without question regeneration
- Completed results review mode displaying official backend score and question-by-question outcomes
- Per-question attempt timeline showing all historical attempts sequentially
- Provenance viewer with source document attribution and frozen evidence citations
- Graceful rendering of deleted source documents as "Archived Document"
- "Retake Revision" action pre-filling setup configuration for a fresh session

### Phase 5 — Cross-Phase Integration, Guest Migration, QA & Documentation
- Dedicated cross-phase integration test suite (`backend/tests/test_m4_integration.py`, 7 comprehensive tests)
- End-to-end verification of guest-to-account migration preserving revision sessions, questions, and attempts
- Document deletion durability verification ensuring questions, attempts, and frozen evidence survive source document deletion (`ON DELETE SET NULL`)
- Multi-document provenance isolation ensuring per-question citations do not collapse across documents
- Cross-identity access control and attempt isolation across users and guests
- Guest AI quota lifecycle verification: MCQ consumes 0 quota, open-ended consumes 1 on success, 0 on failure, 403 on exhaustion while allowing MCQ practice
- Full regression verification across frontend and backend test suites

## Learned

- **Question != Attempt Separation**: Decoupling the immutable question prompt from student submissions enables clean attempt histories, retries, and accurate auditability without data corruption.
- **Dual Evaluation Pathways**: Making MCQ evaluation deterministic in Python avoids unnecessary LLM latency, eliminates quota drain, and ensures 100% reliable scoring.
- **Durable Evidence Citations**: Persisting verbatim `evidence_snippet` text and metadata directly on the question row decouples study history from the lifecycle of the underlying document files.
- **Authoritative Backend Scoring**: Computing the official session score exclusively on the backend upon completion guarantees consistency between summary lists, detail views, and attempt histories.

## Problems Faced

- TestClient cookie retention across requests caused cross-identity test requests to inadvertently inherit previous session cookies.
- Open-ended evaluation prompt contained template words "incorrect" and "irrelevant" which triggered false-positive evaluation matches in test mock providers when checking the whole prompt.
- Manual QA identified that the Revision setup page extended below the viewport without vertical scrolling due to flex constraints.
- Switching between "New Revision" and "Session History" caused in-progress setup configuration (document selection, mode, count) to reset.
- Frontend session creation dispatched camelCase fields (`documentIds`, `questionCount`, `questionType`) which failed Pydantic validation when not normalized.
- Retake button and result status banners (Correct/Needs Improvement) had poor contrast in dark mode due to inverted slate-900 CSS tokens.

## Solutions

- Explicitly cleared and set client cookies (`client.cookies.clear()`, `client.cookies.set(...)`) between identities in tests.
- Isolated the student's submission section in the mock AI provider by extracting text between `"Student's Submitted Answer:"` and `"Evaluation Guidelines:"`.
- Added `min-h-0 overflow-y-auto` to the Revision page `<main>` element, enabling smooth, standard vertical scrolling across all viewports.
- Lifted `setupState` and `selectedDocuments` state to `RevisionPage` to preserve user configuration during tab switching.
- Updated `api/revision.js` to normalize both snake_case and camelCase parameters (`document_ids ?? documentIds`, etc.) prior to backend dispatch.
- Re-styled Retake button with standard secondary action styling (`border-slate-300 bg-surface text-slate-700 hover:bg-slate-50`), added full dark mode `--color-emerald-*` and `--color-rose-*` tokens in `index.css`, and presented the official backend score alongside a secondary informational "Best Attempt" metric when multiple attempts exist.

## Verification

- Focused M4 integration tests: **7 passed** in 3.67s (`test_m4_integration.py`)
- Full backend test suite: **612 passed, 5 skipped** in 75.55s
- Full frontend test suite: **288 passed, 0 failed** in 2.65s (`npm test`)
- Production frontend build: **successful** (`npm run build`, 0 errors)
- Database schema: single Alembic head **`74eb271ec556`**, 0 new migrations, 0 new dependencies
- Repository status: `git diff --check` clean, zero blockers

## Result

V3 Milestone 4 is complete. LearnFlow provides a robust, multi-document Revision Experience 2.0 with persistent revision sessions, deterministic MCQ scoring, rubric-guided AI evaluation, attempt tracking, and document deletion durability.