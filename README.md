# LearnFlow

LearnFlow is an AI-powered learning assistant that helps students study from PDF documents.

---

## Highlights

- Upload and manage PDF documents
- Generate AI-powered summaries, flashcards, quizzes, and mind maps
- Resume learning from previously uploaded documents
- Export learning materials as Markdown
- Built with a provider-swappable AI architecture
- Semantic document indexing (RAG foundation)

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

### 🔮 Planned Next

- Chat with PDF
- Multi-document Chat
- DOCX / PPTX support
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
- Provider abstraction layer

---

## Documentation

- `docs/architecture.md`
- `docs/DEVLOG.md`

---
