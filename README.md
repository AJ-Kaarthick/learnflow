# LearnFlow

LearnFlow is an AI-powered learning assistant that helps students study from PDF documents.

## Features

Current features:

- 📄 Upload PDF documents
- 📑 Extract text from PDFs
- 🤖 Generate AI-powered summaries using Gemini
- 🧠 Generate AI-powered flashcards
- 📝 Generate AI-powered quizzes
- 💾 Store documents, summaries, flashcards, and quizzes in SQLite
- 🔄 AI provider abstraction for future model support

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
- JSON parsing and validation
- Reuse of AI provider abstraction

### ✅ Milestone 4
- AI quiz generation
- Quiz caching
- Shared structured-output parser
- Reuse of AI provider abstraction

### 🚧 Upcoming
- Chat with document
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
pip install -r requirements-dev.txt
cp .env.example .env
```

Add your Gemini API key to `.env`:

```env
GEMINI_API_KEY=your_api_key
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
```

Run:

```bash
uvicorn app.main:app --reload --port 8000
```

Run tests:

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