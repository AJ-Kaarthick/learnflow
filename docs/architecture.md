# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs into AI-powered learning material and enables grounded question answering using Retrieval-Augmented Generation (RAG).
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

├── PDF Service

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


## Current Milestones

### ✅ Milestone 0
- Project setup

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

Current Release:V2.1.0 


Open Existing Document
        OR
Upload New PDF

↓

Document Library

↓

Generate or Restore Cached AI Content

↓

Summary
Flashcards
Quiz
Mind Map
Chat with PDF


## RAG Foundation (V2.0)

LearnFlow now includes the foundational infrastructure required for Retrieval-Augmented Generation (RAG).

### Write Path

PDF

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

The RAG foundation now powers Chat with PDF. Retrieved chunks are passed to the existing AI provider, which generates grounded answers while preventing responses that cannot be supported by the indexed document.

### Chat Pipeline

Question
        │
        ▼
Semantic Retrieval

↓

Relevant Chunks

Conversation History
        │
        ▼

Grounded Prompt

↓

Gemini

↓

Grounded Answer

↓

Relevant Chunks

↓

Grounded Prompt

↓

Gemini

↓

Grounded Answer

↓

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