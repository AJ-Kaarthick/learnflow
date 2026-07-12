# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs into AI-powered learning material such as summaries, flashcards, quizzes, and mind maps.

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

---

## Design Principles

- Thin routes
- Business logic inside services
- Provider-swappable AI architecture
- Shared structured-output parsing
- Environment-based configuration
- Frontend communicates only through the API layer
- Database models are separated from API schemas

---

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

**Current Release:** V1.0

Core learning workflow:

Upload PDF

↓

Extract Text

↓

Generate Summary

↓

Generate Flashcards

↓

Generate Quiz

↓

Generate Mind Map