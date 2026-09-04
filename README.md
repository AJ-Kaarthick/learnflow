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
- 💾 Store generated learning content in SQLite
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

#### Milestone 1 — Authentication & Guest Access
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

#### Milestone 2 — Database & User Data Architecture
- PostgreSQL
- User relationships and ownership
- Conversation ownership
- Document ownership
- Revision data model
- SQLite migration
- Database migrations
- Proper data isolation

#### Milestone 3 — Study Experience 2.0
- AI-generated structured learning content
- Learn mode
- Visualize mode
- Topic-focused study
- Adaptive learning structure
- Contextual learning actions
- Learning-style controls
- Multi-document study
- Grounded study content

#### Milestone 4 — Revision Mode
- Dedicated Revision environment
- Practice questions
- Answer evaluation
- Quiz sessions
- Flashcards
- Revision history
- Difficulty-aware practice
- Document/topic-based revision

#### Milestone 5 — Learning Intelligence & Progress
- Topic-level performance tracking
- Weak-topic detection
- Mastery estimation
- Progress over time
- Difficulty-aware performance
- Revision recommendations
- Adaptive revision
- Flashcard performance
- Spaced-repetition foundation

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
- SQLite

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

### Planned

- Advanced conversation management improvements
- Authentication
- PostgreSQL
- Docker
- Deployment