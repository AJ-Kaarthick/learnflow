# LearnFlow

Upload a PDF and get an AI-generated summary, flashcards, and a quiz.
Built as a learning project — see `docs/architecture.md` (added in a later
milestone) for the full design writeup.

## Project status

**Milestone 0 complete:** backend and frontend scaffolding, wired together.
No AI features yet.

## Running locally

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — you should see `{"status": "ok", ...}`.

Run tests with `.venv/bin/pytest`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Visit the URL Vite prints (usually `http://localhost:5173`). You should see
a green dot and "Backend is connected" — that confirms both services are
talking to each other.

## Tech stack

- **Backend:** FastAPI (Python), SQLite (via SQLAlchemy)
- **Frontend:** React + Vite, Tailwind CSS
- **AI:** provider-swappable layer (currently Gemini)
