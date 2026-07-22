# LearnFlow

LearnFlow is an AI-powered learning assistant that helps students study from PDF documents.

---

## Features

Current features:

- 📄 Upload PDF documents
- 📑 Extract text from PDFs
- 🤖 Generate AI-powered summaries
- 🧠 Generate AI-powered flashcards
- 📝 Generate AI-powered quizzes
- 🗺️ Generate AI-powered mind maps
- 💾 Store generated learning content in SQLite
- 🔄 Provider-swappable AI architecture

---

## Project Status

### ✅ Milestone 1
- PDF upload
- PDF text extraction
- SQLite database
- SQLAlchemy ORM
- React + FastAPI integration

### ✅ Milestone 2
- AI summarization
- Gemini integration
- Provider abstraction
- Summary caching

### ✅ Milestone 3
- AI flashcard generation
- Flashcard caching
- Structured JSON parsing

### ✅ Milestone 4
- AI quiz generation
- Quiz caching
- Shared structured-output parser

### ✅ Milestone 5 (V1 Complete)
- AI mind map generation
- Interactive mind map visualization
- Tree-based JSON generation
- Shared AI architecture reused across all features

## 🚧 LearnFlow V1.1 Progress

### ✅ Milestone 1 — UX Improvements

Completed:

- Clear previous AI-generated content when uploading a new PDF
- Loading indicators for uploads and AI generation
- Disable buttons while requests are running
- Friendly user-facing success and error messages
- Empty states for AI panels
- Client-side PDF validation
- Same-file upload support

### ✅ Milestone 2 — UI Polish

Completed:

- Improved visual hierarchy
- Consistent card-based layout
- Better typography and spacing
- Unified button styling
- Responsive layout improvements
- Accessibility improvements
- Consistent accent color system

### ✅ Milestone 3 — Document Manager

Completed:

- Copy Summary
- Download Summary
- Copy Flashcards
- Copy Quiz
- Document history
- Open existing documents
- Rename documents
- Delete documents
- Restore cached AI-generated content
- Refresh-and-continue workflow

---

## Running Locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Add your Gemini API key to `.env`:

```env
GEMINI_API_KEY=your_api_key
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
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

## Roadmap

### ✅ V1
- PDF Upload
- Text Extraction
- AI Summaries
- AI Flashcards
- AI Quizzes
- AI Mind Maps

### 🚧 V1.1

#### ✅ Milestone 1
- UX improvements
- Loading indicators
- Client-side validation
- Better error handling
- Empty states
- Same-file upload support

#### ✅ Milestone 2
- UI polish
- Better spacing
- Better typography
- Better cards
- Better responsiveness
- Accessibility improvements

### ✅ Milestone 3 — Document Manager

Completed:

- Copy Summary
- Download Summary
- Copy Flashcards
- Copy Quiz
- Persistent document history
- Open existing documents
- Rename documents with locked file extension
- Delete documents
- Restore cached AI-generated content
- Refresh-and-continue workflow

#### ⏳ Milestone 4

- Search documents
- Sort documents
- Better document metadata

#### ⏳ Milestone 5
- Documentation
- Final testing
- Release preparation

### 🔮 V2
- Chat with PDF (RAG)
- DOCX / PPTX / TXT support
- Authentication
- PostgreSQL
- Docker
- Deployment