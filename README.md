# LearnFlow

LearnFlow is an AI-powered study workspace that transforms PDF documents into summaries, flashcards, quizzes, mind maps, and grounded AI conversations using Retrieval-Augmented Generation (RAG).
---

## Highlights

- Upload and manage PDF documents
- Generate AI-powered summaries, flashcards, quizzes, and mind maps
- Resume learning from previously uploaded documents
- Export learning materials as Markdown
- Built with a provider-swappable AI architecture
- Semantic document indexing (RAG foundation)
- Chat with PDF using Retrieval-Augmented Generation (RAG)
- Multi-turn conversational memory for natural conversations
- Multi-document Chat
- History-aware conversational retrieval for natural follow-up questions
- Persistent AI learning workspace
- Workspace session persistence
- Per-document conversation history
- Automatic workspace restoration after refresh

---

## Features

LearnFlow currently supports:

- 📄 Upload PDF documents
- 📑 Extract text from PDFs
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
- 📄 Display file size and page count
- 📋 Copy summaries, flashcards, and quizzes
- 💾 Download summaries, flashcards, quizzes, and mind maps as Markdown
- 💾 Store generated learning content in SQLite
- 🔄 Provider-swappable AI architecture
- 🧩 Semantic document indexing (RAG foundation)
- 🔎 Semantic search over indexed documents
- 💬 Chat with PDF documents using Retrieval-Augmented Generation (RAG)
- 🧠 Multi-turn conversational memory
- 🧭 History-aware conversational retrieval
- 📚 Multi-document Chat
- 📖 Grounded responses with supporting source references
- 💾 Workspace session persistence
- 💬 Per-document conversation history
- 🔄 Multi-document conversation persistence
- 📂 Automatic workspace restoration after refresh
- 🆕 New Conversation for independent chat sessions
- 📑 Persistent study tab selection

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


### 🚧 V2.1

#### Milestone 1 ✅
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


#### Milestone 2 ✅
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


### 🔮 Planned Next

#### V2.1
- Theme Customization

#### V2.2
- DOCX Support
- PPTX Support

#### V3
- Authentication
- PostgreSQL
- Docker
- Deployment

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
- Chat with PDF
- Conversational Memory
- Multi-document Chat
- History-aware Conversational Retrieval
- Workspace UX Polish
- Workspace Session Persistence

### Planned
- 🔜 DOCX / PPTX support
- 🔜 Authentication
- 🔜 PostgreSQL
- 🔜 Docker
- 🔜 Deployment
- 🔜 Query Rewriting


## Future Roadmap

### V2.1

Milestone 3
- Theme Customization
- Light / Dark mode
- Accent colors

### V2.2

- DOCX Support
- PPTX Support

### V3

- Authentication
- PostgreSQL
- Docker
- Deployment