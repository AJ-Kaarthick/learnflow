# LearnFlow Architecture

## Goal

LearnFlow converts uploaded PDFs into AI-powered learning material.

---

## Tech Stack

Frontend
- React
- Vite
- Tailwind

Backend
- FastAPI

Database
- SQLite

AI
- Gemini (later replaceable)

---

## Request Flow

User

↓

React UI

↓

API Layer

↓

FastAPI Route

↓

Business Services

↓

Database / Storage

↓

JSON Response

↓

React UI

---

## Folder Responsibilities

frontend/
    UI

backend/app/api/
    HTTP endpoints

backend/app/services/
    Business logic

backend/app/db/
    Database

backend/app/schemas/
    API contracts

backend/app/core/
    Configuration

---

## Current Milestones

Milestone 0
- Project setup

Milestone 1
- PDF upload
- Text extraction

Milestone 2
- AI summarization

Milestone 3
- Flashcards

Milestone 4
- Quiz generation