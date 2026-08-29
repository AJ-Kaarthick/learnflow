# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs, DOCX, PPTX, and supported image documents with extractable text into AI-powered learning material and enables grounded question answering using Retrieval-Augmented Generation (RAG).

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
- Server-backed persistent chat conversations
- Conversation history is persisted server-side
- Recent conversation provides conversational context only
- Conversation history is never used as factual evidence
- Retrieval is performed using the current user query
- Prompt construction combines retrieved document context with recent conversation
- Documents remain the single source of truth

- Document extraction is format-agnostic and dispatches processing based on document type
- OCR is used when document content is image-based or requires text recognition
- OCR failures are logged with actionable diagnostics
- System-level OCR dependencies are checked at application startup
- Document readiness is validated before document-based AI generation
- Unreadable documents do not block readable documents in multi-document Chat
- Documents remain the single source of truth for document metadata and content


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


## UX Principles (V2 — Legacy Chat Architecture)

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


## Workspace Persistence (V2.1 — Legacy Conversation Storage)

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

> **V2.4 update:** Conversation persistence is being migrated from client-side localStorage to server-backed conversation records. The legacy localStorage conversation state remains relevant during the migration phase.

---

## Version

Current Version:
V2.4 — In Progress

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


## V2.4 — Document Readiness and Chat UX

V2.4 adds document-content validation and improved handling of documents that do not contain readable text.

Before document-based AI generation, the system now verifies that readable document content is available.

'''text
Document
   ↓
Document Readiness
   ↓
Readable text available?
   ├── NO  → No-readable-text state
   │
   └── YES → AI generation / Chat
'''
   
### Conversation Architecture

LearnFlow uses persistent conversations for AI chat.

V2.4 introduces server-backed persistent conversations. The conversation
architecture is being implemented incrementally across multiple phases.

**Implemented so far:**

- Conversation and Message persistence
- Conversation-document associations
- Conversation CRUD APIs
- Persistent message/RAG endpoint
- Database-backed conversation history
- Persistent source and grounding metadata
- Frontend conversation management
- Conversation creation and switching
- Conversation deletion
- Conversation rename support
- Persistent conversation history restoration
- Chat document-selection synchronization
- Conversation timestamp handling
- Regression coverage for conversation lifecycle and persistence behavior

**Planned next:**

- Automatic conversation title generation
- Further migration from localStorage conversation state to server persistence
- Further improvements to persistent conversation document context

A conversation consists of:

Conversation
├── Messages
└── ConversationDocuments
        └── Documents


### V2.4 Conversation Persistence

The original V2 chat architecture used client-managed conversation history and
stateless chat requests.

V2.4 introduces server-backed persistent conversations and messages. The
conversation records and message history are now persisted in SQLite, while the
underlying RAG retrieval architecture remains unchanged.

This migration is being performed incrementally, with legacy localStorage
conversation state retained where required during the transition.  

### Chat Document Selection

Chat document selection is maintained independently from ordinary document
opening behavior.

Adding a document through the Chat upload workflow merges the newly uploaded
document into the current Chat selection rather than replacing the existing
selection.

Duplicate document selections are prevented.

Unreadable documents are identified and do not prevent readable documents from
being used for Chat.

### Frontend Conversation Management

The Chat workspace provides a persistent conversation interface backed by
server-side conversation records.

User
 ↓
Chat Sidebar
 ↓
Conversation Selection
 ↓
Conversation API
 ↓
Persistent Conversation
 ↓
Persistent Messages
 ↓
Chat Workspace

The frontend supports:

- Creating conversations
- Listing conversations
- Switching conversations
- Renaming conversations
- Deleting conversations
- Restoring conversation history
- Maintaining the selected document context

#### Conversation

Stores conversation metadata such as:
- id
- title
- title_is_custom
- created_at
- updated_at

#### Message

Stores:
- id
- conversation_id
- role
- content
- position
- sources_json
- grounded
- created_at

#### ConversationDocument

Associates conversations with documents through a many-to-many relationship.

A document can belong to multiple conversations, and a conversation can contain multiple documents.

The association uses a composite primary key:

(conversation_id, document_id)


### Conversation API

POST   /conversations
GET    /conversations
GET    /conversations/{id}
PATCH  /conversations/{id}
DELETE /conversations/{id}
PUT    /conversations/{id}/documents


Conversation persistence is introduced incrementally.

The backend foundation is implemented first. Message persistence, RAG integration, frontend conversation management, title generation, document-context management, and migration from the existing client-side conversation state are implemented in subsequent phases.


### Persistent Conversation Message Flow

User Question
      ↓
Conversation
      ↓
Conversation Documents
      ↓
Persistent Conversation History
      ↓
History-aware Retrieval
      ↓
Semantic Retrieval
      ↓
Grounded Answer Generation
      ↓
Persist User + Assistant Messages
      ↓
Update Conversation Activity


Message persistence occurs only after successful AI generation. This
prevents failed AI requests from creating incomplete or misleading
conversation history.

Retrieved source references and grounding metadata are stored with the
assistant message so previous responses remain interpretable even if
document state changes later.