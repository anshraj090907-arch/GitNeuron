from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import indexing
from app.core.github_service import repo_id_for
from app.models import IndexRequest, IndexStatus

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.post("", response_model=IndexStatus)
def index_repository(req: IndexRequest) -> IndexStatus:
    if "github.com" not in req.repo_url:
        raise HTTPException(status_code=400, detail="Please provide a github.com repository URL.")
    repo_id = indexing.start_indexing(req.repo_url, req.branch)
    status = indexing.get_status(repo_id)
    return status or IndexStatus(repo_id=repo_id, status="pending")


@router.get("/{repo_id}/status", response_model=IndexStatus)
def get_status(repo_id: str) -> IndexStatus:
    status = indexing.get_status(repo_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown repo_id.")
    return status


@router.get("/{repo_id}/files")
def get_file_tree(repo_id: str) -> dict:
    """Backs the file-structure explorer — the synopsis's 'understands file structure' feature."""
    status = indexing.get_status(repo_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown repo_id.")
    tree = indexing.get_file_tree(repo_id)
    if tree is None:
        raise HTTPException(status_code=409, detail="File tree isn't available yet.")
    return tree


@router.get("/resolve")
def resolve(repo_url: str, branch: str | None = None) -> dict:
    return {"repo_id": repo_id_for(repo_url, branch)}
