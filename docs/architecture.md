# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs, DOCX, PPTX, and image documents into AI-powered learning material and enables grounded question answering using Retrieval-Augmented Generation (RAG).

---

## Tech Stack

### Frontend
- React
- Vite
- Tailwind CSS

### Backend
- FastAPI

### Database
- SQLite
- SQLAlchemy ORM

### AI
- Gemini
- Provider abstraction layer

---

## Request Flow

User

↓

React UI

↓

Frontend API Layer

↓

FastAPI Route

↓

Business Services

├── Storage Service

├── Document Extraction Service
        ├── PDF Service
        └── DOCX Service
        └── PPTX Service
        └── OCR Service        
├── Summary Service

├── Flashcard Service

├── Quiz Service

└── MindMap Service

↓

AI Provider

↓

Structured Output Utilities

↓

Gemini

↓

Database / Storage

↓

JSON Response

↓

React UI

## Chat Request Flow (V2)

User

↓

React UI

↓

Frontend API Layer

↓

Chat Route

↓

Chat Service

↓

Conversation History
                │
                ▼
Grounded Prompt Builder

Question
        │
        ▼
Retrieval Service

↓

Embedding Provider

↓

Relevant Chunks

↓

Grounded Prompt Builder

↓

AI Provider

↓

Grounded Answer

↓

Supporting Sources

↓

JSON Response

---

## Folder Responsibilities

frontend/
- User interface

frontend/src/api/
- API communication layer

backend/app/api/
- HTTP endpoints

backend/app/services/
- Business logic
- Chat orchestration

backend/app/services/ai/
- AI provider abstraction
- Provider implementations
- Structured output utilities

backend/app/db/
- Database models

backend/app/schemas/
- API request/response schemas

backend/app/core/
- Configuration

backend/app/services/rag/
- Chunking
- Embedding orchestration
- Semantic retrieval


backend/app/services/document_extraction_service.py
- Dispatches extraction by document type

backend/app/services/docx_service.py
- DOCX text extraction

backend/app/services/pptx_service.py
- PPTX text extraction

backend/app/services/ocr/
- OCR processing for image documents and scanned PDF pages
- OCR dependency detection and diagnostics


---

## Design Principles

- Thin routes
- Business logic inside services
- Provider-swappable AI architecture
- Shared structured-output parsing
- Environment-based configuration
- Frontend communicates only through the API layer
- Database models are separated from API schemas
- Retrieval separated from generation
- Embedding-provider abstraction
- Idempotent document indexing
- Retrieval is performed before generation
- Answers are grounded in retrieved document context
- Chat does not implicitly trigger indexing
- Stateless chat requests
- Conversation history is client-managed
- Recent conversation provides conversational context only
- Conversation history is never used as factual evidence
- Retrieval is performed using the current user query
- Prompt construction combines retrieved document context with recent conversation
- Documents remain the single source of truth

- Document extraction is format-agnostic and dispatches processing based on document type
- OCR is used when document content is image-based or requires text recognition
- OCR failures are logged with actionable diagnostics
- System-level OCR dependencies are checked at application startup


### Hallucination Prevention

LearnFlow prevents hallucinations by ensuring:

- Documents are the only factual source.
- Conversation history only resolves references.
- Retrieval always happens before generation.
- If retrieval finds no supporting content, the model returns a fixed "not found" response.


## UX Principles (V1.1)

The V1.1 update focuses on improving usability without changing the underlying architecture.

Implemented in V1.1 so far:

- Immediate client-side validation
- Loading feedback during long-running requests
- Disabled controls while requests are active
- Friendly error messages
- Empty states for AI panels
- Automatic reset of previous AI content after uploading a new document
- Improved visual hierarchy
- Consistent card layout
- Better responsive design
- Built-in copy and download actions for generated content
- Persistent document management
- Reopen previously uploaded documents
- Restore cached AI-generated content
- Document rename and delete support
- Original file extensions remain visible and are preserved during document renaming

## UX Principles (V1.2)

V1.2 focuses on making LearnFlow scale well as the number of uploaded documents grows.

Implemented:

- Scrollable Document Library
- Search by filename
- Sorting
- Recently Opened
- Better rename validation
- Inline validation errors
- Upload date display
- Last opened display
- File size display
- Page count display
- Compact responsive metadata layout
- Markdown export for summaries
- Markdown export for flashcards
- Markdown export for quizzes
- Markdown export for mind maps
- Shared frontend Markdown export utilities
- Consistent download workflow across all learning artifacts


## UX Principles (V2)

V2 introduces conversational interaction while preserving the existing application architecture.

Implemented:

- Integrated Chat with PDF panel
- Automatic document indexing on first use
- Local conversation history
- Automatic conversation reset when switching documents
- Grounded AI responses
- Expandable supporting source references
- Consistent chat interface matching existing LearnFlow styling
- Multi-turn conversations
- Natural multi-turn conversations
- Conversation history preserved during active sessions
- Recent history automatically trimmed


---

## UX Principles (V2.1)

Implemented:

- Unified three-panel workspace
- Automatic single-document chat synchronization
- Multi-document selection workflow
- Independent scrolling for chat and study workspace
- Sticky chat composer
- Guided empty workspace
- Improved spacing and visual hierarchy
- Floating "Scroll to latest" action
- Better responsive flex layouts
- Browser page scroll prevention
- Search input overflow fixes
- Workspace session persistence
- Automatic workspace restoration
- Per-document conversation persistence
- Multi-document conversation persistence
- Persistent study tab selection
- Persistent library state
- Persistent document selection
- New Conversation workflow
- Theme customization
- Light / Dark / System themes
- Accent color system
- Workspace personalization
- Comfortable & Compact density modes
- Persistent appearance settings
- Reduced motion support
- Accessibility improvements
- GitHub-flavored Markdown rendering
- Keyboard shortcuts
- Keyboard shortcuts dialog
- Copy AI responses
- Regenerate responses
- Stop generation
- Chat timestamps
- Improved source presentation
- Shared modal infrastructure
- Improved loading indicators


## Workspace Persistence (V2.1)

Frontend workspace state is persisted locally to provide seamless continuity across page refreshes and browser restarts.

Persisted state includes:

- Active document
- Active study tab
- Selected documents
- Search query
- Sort preference
- Library scroll position
- Per-document conversations
- Multi-document conversations

Persistence is implemented through a centralized frontend persistence utility using browser localStorage.

Conversation state is keyed by document IDs rather than filenames, ensuring conversations survive document renames.

Multi-document conversations are keyed using sorted document IDs so identical document sets always restore the same conversation regardless of selection order.

## Current Milestones

### ✅ Milestone 0
- Project setup
- Workspace Session Persistence

### ✅ Milestone 1
- PDF upload
- PDF storage
- PDF text extraction

### ✅ Milestone 2
- AI summarization
- Gemini integration
- Provider abstraction
- Summary caching

### ✅ Milestone 3
- AI flashcards

### ✅ Milestone 4
- AI quizzes

### ✅ Milestone 5
- AI mind maps

---

## Version

Current Version:
V2.2 Complete 

Open Existing Document
        OR
Upload PDF / DOCX / PPTX

↓

Document Library

↓

Generate or Restore Cached AI Content

↓

Summary
Flashcards
Quiz
Mind Map
Chat with Documents


## RAG Foundation (V2.0)

LearnFlow now includes the foundational infrastructure required for Retrieval-Augmented Generation (RAG).

### Write Path

Document

↓

Chunking Service

↓

Embedding Provider

↓

DocumentChunk Table

### Read Path

User Query

↓

Embedding Provider

↓

Semantic Retrieval

↓

Relevant Chunks

The RAG foundation powers every conversational feature in LearnFlow, including single-document and multi-document grounded chat. Retrieved chunks are passed to the existing AI provider, which generates grounded answers while preventing responses that cannot be supported by the indexed document.


### Chat Pipeline

User Question
        │
        ▼
Conversation History
        │
        ▼
History-aware Query Rewriting (if needed)
        │
        ▼
Semantic Retrieval
        │
        ▼
Relevant Chunks
        │
        ▼
Grounded Prompt
        │
        ▼
Gemini
        │
        ▼
Grounded Answer
        │
        ▼
Supporting Sources


## Conversational Retrieval (V2 Milestone 6)

Traditional semantic retrieval only considers the user's current question.

Conversational Retrieval first rewrites follow-up questions into standalone queries using recent conversation history.

Example:

User:
What is ls?

↓

Explain it.

↓

Retrieval Query:

Explain the Linux "ls" command.

The rewritten query is used only for retrieval.

The original user question is still passed to the AI model.

Conversation history never becomes factual evidence.

Retrieved document chunks remain the only source of truth.



Workspace

┌──────────────┬──────────────────────┬───────────────┐
│ Library      │ Study Workspace      │ AI Assistant  │
│              │                      │               │
│ Upload       │ Summary              │ Chat          │
│ Search       │ Flashcards           │ Sources       │
│ Sort         │ Quiz                 │ Conversation  │
│ Documents    │ Mind Map             │               │
└──────────────┴──────────────────────┴───────────────┘


## Multi-format Document Pipeline (V2.3)

Uploaded Document

↓

Document Extraction Service

├── PDF
├── DOCX
├── PPTX
└── OCR
    ├── Image Documents
    └── Scanned PDF Pages

↓

Extracted Text

↓

Chunking

↓

Embeddings

↓

Semantic Retrieval

↓

AI Features

• Summary
• Flashcards
• Quiz
• Mind Map
• Chat


## V2.3 — OCR and Document Processing Improvements

V2.3 extends LearnFlow's document pipeline beyond text-native documents by adding OCR support for image documents and scanned PDFs.

OCR processing integrates with the existing document extraction pipeline, allowing OCR-extracted text to flow through the same chunking, embedding, retrieval, and AI-generation pipeline as normal document text.

The application checks for required system-level OCR dependencies at startup and logs actionable warnings when they are unavailable.

Document extraction failures are logged with the underlying exception and document context, making unsupported or incorrectly configured environments diagnosable without changing document status behavior.


## Generated Content Persistence

Generated summaries, flashcards, quizzes, and mind maps are synchronized with the workspace's cached content state after generation.

This ensures generated content survives study-tab switches, where individual study panels may be unmounted and remounted.

The existing backend persistence remains the source of truth across document reloads and refreshes.