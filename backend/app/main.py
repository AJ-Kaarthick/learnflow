from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

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


@app.get("/health")
def health_check() -> dict:
    """
    Simple liveness check. The frontend calls this on load to confirm
    it can reach the backend. Later, tools like uptime monitors or
    deployment platforms also ping endpoints like this to check the
    service is alive.
    """
    return {"status": "ok", "service": "learnflow-backend", "env": settings.app_env}
