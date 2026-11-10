"""Shared Pydantic schemas for requests and responses."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    repo_url: str = Field(..., description="HTTPS GitHub repository URL")
    branch: str | None = Field(default=None, description="Branch to index; defaults to the repo's default branch")


class IndexStatus(BaseModel):
    repo_id: str
    status: Literal["pending", "validating", "cloning", "chunking", "embedding", "ready", "error"]
    message: str = ""
    files_indexed: int = 0
    chunks_indexed: int = 0
    repo_name: str = ""
    default_branch: str = ""


class ReasoningStep(BaseModel):
    """One node of the live agent reasoning canvas."""

    id: str
    label: str
    kind: Literal["plan", "retrieval", "generation", "tool", "fallback", "error"]
    detail: str = ""
    status: Literal["running", "done", "failed"] = "done"


class FileTreeNode(BaseModel):
    name: str
    type: Literal["dir", "file"]
    path: str | None = None
    children: list["FileTreeNode"] = Field(default_factory=list)


class Template(BaseModel):
    id: str
    name: str
    description: str


class ModelOption(BaseModel):
    id: str              # "provider:model" — what the client sends back as model_override
    provider: str
    model: str
    label: str
    configured: bool     # whether this backend currently has a key for its provider
    is_default_chain: bool  # part of the automatic fallback chain, in order


class SourceChunk(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    language: str
    snippet: str
    score: float


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    history: list[dict] = Field(default_factory=list)  # [{role, content}]
    model_override: str | None = None  # "provider:model", optional explicit pick
    template_id: str | None = None  # selected template/mode, see core/templates.py


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    reasoning: list[ReasoningStep]
    model_used: str


class ExportGistRequest(BaseModel):
    title: str
    content: str


class ExportPdfRequest(BaseModel):
    title: str
    content: str
    sources: list[SourceChunk] = Field(default_factory=list)


class ExportSandboxRequest(BaseModel):
    title: str
    files: dict[str, str]  # path -> content
