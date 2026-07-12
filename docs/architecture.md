# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs into AI-powered learning material.

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

└── Quiz Service

↓

AI Provider

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
- Frontend API layer

backend/app/api/
- HTTP endpoints

backend/app/services/
- Business logic

backend/app/services/ai/
- AI provider abstraction, provider implementations, and structured output utilities

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
- AI provider abstraction
- Shared structured-output parsing
- Environment-based configuration
- Frontend communicates through the API layer
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
- AI flashcard generation
- Flashcard caching
- Reuse of AI provider abstraction

### ✅ Milestone 4
- AI quiz generation
- Quiz caching
- Shared structured-output parser