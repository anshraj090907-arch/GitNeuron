"""
Central configuration for GitNeuron's backend.

Every value here can be overridden by an environment variable (or an
entry in a local .env file), which keeps the service model-agnostic:
swapping the default LLM or embedding model never requires touching
code — only configuration.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- storage ---------------------------------------------------------
    data_dir: Path = Path("./data")
    repos_dir: Path = Path("./data/repos")
    index_dir: Path = Path("./data/index")

    # --- GitHub ------------------------------------------------------------
    github_token: str | None = None  # optional, raises rate limits / enables private repos

    # --- embeddings ----------------------------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- chunking --------------------------------------------------------
    max_chunk_tokens: int = 400
    chunk_overlap_tokens: int = 40
    max_repo_chunks: int = 2500  # safety cap for CPU embeddings to prevent hangs on massive repos

    # --- retrieval -------------------------------------------------------
    top_k: int = 5

    # --- LLM provider chain ----------------------------------------------
    # First entry is the primary model; the rest are automatic fallbacks
    # used by the autonomous error-recovery layer when a provider call
    # fails or is rate limited. Format: "<provider>:<model>"
    llm_chain: list[str] = [
        "groq:openai/gpt-oss-120b",
        "groq:qwen/qwen3.8-27b",
        "anthropic:claude-sonnet-4-5",
        "openai:gpt-4o-mini",
        "gemini:gemini-1.5-flash",
    ]

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    deepseek_api_key: str | None = None
    groq_api_key: str | None = None  # used for Llama / Qwen via Groq's OpenAI-compatible API

    # --- export ------------------------------------------------------------
    github_gist_token: str | None = None  # falls back to github_token if unset

    # --- server ------------------------------------------------------------
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.repos_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    return settings
