from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import chat, export, model_catalog, repos, templates

settings = get_settings()

app = FastAPI(
    title="GitNeuron API",
    description="Chat with any GitHub repository, grounded in its actual code via RAG.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos.router)
app.include_router(chat.router)
app.include_router(export.router)
app.include_router(templates.router)
app.include_router(model_catalog.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
