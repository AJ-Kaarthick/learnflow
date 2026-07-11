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