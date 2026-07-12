# LearnFlow Development Log

---

# Milestone 0 — Project Scaffolding

**Date:** 11 July 2026

## Objective

Create a production-style project structure and verify the backend and frontend communicate successfully.

## Completed

- Created GitHub repository
- Cloned repository locally
- Set up FastAPI backend
- Set up React + Vite frontend
- Configured Tailwind CSS
- Created Python virtual environment
- Installed backend dependencies
- Installed Node.js using nvm
- Installed frontend dependencies
- Verified `/health` endpoint
- Verified frontend successfully communicates with backend

## Learned

- Python virtual environments
- FastAPI project structure
- React + Vite basics
- Tailwind CSS setup
- Git workflow
- Node Version Manager (nvm)
- Environment variables (.env)

## Problems Faced

1. Missing `python3-venv`
2. Git safe.directory warning
3. Node.js v18 incompatible with Vite 8

## Solutions

- Installed `python3.12-venv`
- Configured Git safe.directory
- Installed Node.js LTS using nvm

## Reflection

Milestone 0 taught me that setting up a development environment is a significant part of software engineering. Most issues encountered were related to tooling rather than application code. I now have a working full-stack project foundation that future milestones will build upon.

---

# Milestone 1

## Goal

Implement PDF upload and text extraction.

## Features Completed

- Upload PDF from the React frontend
- Store uploaded PDFs locally
- Extract text using pypdf
- Store document metadata in SQLite
- Retrieve uploaded document by ID
- Display extracted text preview
- Added automated backend tests

## Learned

- FastAPI routing
- SQLAlchemy ORM basics
- File upload using FormData
- React API layer
- Service layer architecture
- SQLite integration
- Backend ↔ Frontend communication

## Problems Faced

- Duplicate backend folder after copying milestone
- Git ignored files verification
- Backend testing and routing verification

## Result

LearnFlow can now upload PDFs, extract their text, store metadata, and display the extracted content through the React frontend.

---

# Milestone 2

## Goal

Implement AI-powered document summarization using a reusable AI architecture.

## Features Completed

- AI-generated summaries
- Gemini integration
- AI provider abstraction
- Summary caching
- Summary API endpoints
- Frontend summary generation
- Backend tests for summarization

## Learned

- Provider abstraction
- Dependency injection
- Environment variables
- AI service architecture
- Summary caching

## Problems Faced

- Gemini model deprecation
- API key accidentally added to `.env.example`
- Dependency version mismatch after SDK upgrade

## Solutions

- Updated to a supported Gemini model
- Removed the exposed API key before committing
- Updated dependencies and verified a clean installation

## Result

LearnFlow can now generate AI summaries while keeping the AI layer modular and reusable for future features like flashcards, quizzes, and document chat.

---

# Milestone 3

## Goal

Implement AI-generated flashcards while reusing the AI infrastructure built in Milestone 2.

## Features Completed

- AI-generated flashcards
- Flashcard database model
- Flashcard caching
- Flashcard API endpoints
- Frontend flashcard generation
- Backend tests for flashcards

## Learned

- Prompting LLMs for structured JSON
- JSON parsing and validation
- Reusing existing service architecture
- Designing reusable AI features

## Problems Faced

- Handling AI responses wrapped in Markdown code fences
- Validating malformed JSON responses
- Reusing existing architecture without duplicating logic

## Result

LearnFlow can now generate and cache AI-powered flashcards while reusing the same provider abstraction introduced in Milestone 2.

---

# Milestone 4

## Goal

Implement AI-generated quizzes while reusing the AI infrastructure built in previous milestones.

## Features Completed

- AI-generated quizzes
- Quiz database model
- Quiz caching
- Quiz API endpoints
- Frontend quiz generation
- Shared structured-output parser
- Backend tests for quizzes

## Learned

- Reusing common parsing logic
- Database design tradeoffs
- JSON columns in SQLAlchemy
- Extending existing architecture without duplication

## Problems Faced

- Designing a reusable JSON parser for multiple AI features
- Choosing between normalized tables and JSON columns
- Keeping the AI provider abstraction generic

## Result

LearnFlow can now generate, cache, and display AI-powered quizzes while reusing the same AI provider abstraction and shared structured-output utilities used by other AI features.

---

# Milestone 5

## Goal

Implement AI-generated mind maps while continuing to reuse the existing AI architecture.

## Features Completed

- AI-generated mind maps
- Mind map database model
- Mind map caching
- Mind map API endpoints
- Interactive frontend visualization
- Shared structured-output utilities
- Backend tests for mind maps

## Learned

- Representing hierarchical data as trees
- Tree validation
- JSON storage for hierarchical structures
- Choosing between JSON storage and normalized database tables
- Reusing existing architecture without introducing new AI abstractions

## Problems Faced

- Choosing an appropriate data structure for mind maps
- Rendering hierarchical AI output on the frontend
- Keeping the implementation reusable while avoiding unnecessary complexity

## Result

LearnFlow V1 is now feature complete. Users can upload PDFs and generate summaries, flashcards, quizzes, and interactive mind maps while reusing a single AI provider abstraction and a shared architecture across all AI features.