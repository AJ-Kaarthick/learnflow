from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    routes_documents,
    routes_flashcards,
    routes_mindmap,
    routes_quiz,
    routes_rag,
    routes_summary,
)
from app.core.config import settings
from app.db.database import Base, engine

# Creates any tables that don't exist yet, based on the models we've
# defined (see db/models.py). Fine for SQLite in V1. A real production
# app would use a migration tool (Alembic) instead, so schema changes
# are tracked and reversible — worth introducing if/when we move to
# Postgres, since "just recreate the table" stops being an option once
# there's real user data in it.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LearnFlow API", version="0.1.0")

# Browsers block requests from one origin (localhost:5173, the React dev
# server) to another (localhost:8000, this API) unless the server
# explicitly allows it. This is CORS. Without this middleware, every
# fetch() call from the frontend would fail silently in the browser
# console with a CORS error — a very common first-project stumbling block.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(routes_documents.router, prefix="/api/v1")
app.include_router(routes_summary.router, prefix="/api/v1")
app.include_router(routes_flashcards.router, prefix="/api/v1")
app.include_router(routes_quiz.router, prefix="/api/v1")
app.include_router(routes_mindmap.router, prefix="/api/v1")
app.include_router(routes_rag.router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict:
    """
    Simple liveness check. The frontend calls this on load to confirm
    it can reach the backend. Later, tools like uptime monitors or
    deployment platforms also ping endpoints like this to check the
    service is alive.
    """
    return {"status": "ok", "service": "learnflow-backend", "env": settings.app_env}
