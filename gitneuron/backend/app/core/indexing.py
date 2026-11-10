"""
Indexing pipeline: validate → clone → chunk → embed → store, with an
in-memory status table so the frontend can poll progress while a large
repository is being processed. Mirrors the synopsis's workflow
flowchart, including the "repository valid and accessible?" gate
before anything is cloned.
"""
from __future__ import annotations

import threading

from app.config import get_settings
from app.core import vectorstore
from app.core.chunking import chunk_repository
from app.core.embeddings import embed_texts
from app.core.github_service import (
    RepoValidationError, build_file_tree, clone_or_fetch, default_branch_of,
    parse_repo_name, render_tree_text, repo_id_for, validate_repo, walk_repo_files,
)
from app.models import IndexStatus

_STATUS: dict[str, IndexStatus] = {}
_FILE_PATHS: dict[str, list[str]] = {}
_LOCK = threading.Lock()


def get_status(repo_id: str) -> IndexStatus | None:
    with _LOCK:
        return _STATUS.get(repo_id)


def get_file_tree(repo_id: str) -> dict | None:
    with _LOCK:
        paths = _FILE_PATHS.get(repo_id)
    if paths is None:
        return None
    return build_file_tree(paths)


def get_file_tree_text(repo_id: str, max_lines: int = 160) -> str | None:
    """Condensed text form of the file tree, for injection into the LLM prompt."""
    tree = get_file_tree(repo_id)
    if tree is None:
        return None
    return render_tree_text(tree, max_lines=max_lines)


def _set_status(repo_id: str, **fields) -> None:
    with _LOCK:
        current = _STATUS.get(repo_id) or IndexStatus(repo_id=repo_id, status="pending")
        updated = current.model_copy(update=fields)
        _STATUS[repo_id] = updated


def start_indexing(repo_url: str, branch: str | None) -> str:
    repo_id = repo_id_for(repo_url, branch)
    _set_status(repo_id, status="pending", repo_name=parse_repo_name(repo_url), message="Queued…")

    thread = threading.Thread(target=_run_indexing, args=(repo_url, branch, repo_id), daemon=True)
    thread.start()
    return repo_id


def _run_indexing(repo_url: str, branch: str | None, repo_id: str) -> None:
    settings = get_settings()
    try:
        _set_status(repo_id, status="validating", message="Checking repository is valid and accessible…")
        try:
            meta = validate_repo(repo_url, branch)
        except RepoValidationError as exc:
            _set_status(repo_id, status="error", message=str(exc))
            return

        owner, name = meta["full_name"].split("/", 1)
        size_mb = meta.get("size_kb", 0) / 1024
        size_str = f" (~{size_mb:.1f} MB)" if size_mb > 0.5 else ""
        _set_status(repo_id, status="cloning", message=f"Cloning repository{size_str}…", repo_name=meta["full_name"])
        dest, used_fallback = clone_or_fetch(
            repo_url, branch, repo_id, owner, name, meta["default_branch"]
        )
        if used_fallback:
            # git clone failed (blocked protocol, flaky network, …) — the
            # tarball fallback already ran. Surface that it happened rather
            # than silently pretending the fast path succeeded.
            _set_status(
                repo_id, status="cloning",
                message="Git clone failed — recovered via GitHub tarball download…",
            )
            actual_branch = branch or meta["default_branch"]
        else:
            actual_branch = default_branch_of(dest)

        _set_status(repo_id, status="chunking", message="Parsing files…", default_branch=actual_branch)
        files = walk_repo_files(dest)
        if not files:
            _set_status(repo_id, status="error", message="No readable text/code files found in this repository.")
            return

        with _LOCK:
            _FILE_PATHS[repo_id] = [f.path for f in files]

        chunks = chunk_repository(files, max_tokens=settings.max_chunk_tokens)
        if len(chunks) > settings.max_repo_chunks:
            chunks = chunks[:settings.max_repo_chunks]

        total_chunks = len(chunks)
        _set_status(
            repo_id, status="embedding",
            message=f"Embedding 0/{total_chunks} chunks (0%) across {len(files)} files…",
            files_indexed=len(files),
            chunks_indexed=0,
        )

        BATCH = 64
        texts = [c.text for c in chunks]
        for i in range(0, len(texts), BATCH):
            batch_chunks = chunks[i:i + BATCH]
            batch_vectors = embed_texts(texts[i:i + BATCH])
            vectorstore.upsert_chunks(repo_id, batch_chunks, batch_vectors)
            done = min(i + BATCH, total_chunks)
            pct = int((done / total_chunks) * 100) if total_chunks else 100
            _set_status(
                repo_id,
                chunks_indexed=done,
                message=f"Embedding chunks: {done}/{total_chunks} ({pct}%)…",
            )

        _set_status(
            repo_id, status="ready",
            message=f"Indexed {len(files)} files / {len(chunks)} chunks.",
            files_indexed=len(files), chunks_indexed=len(chunks),
        )
    except Exception as exc:  # noqa: BLE001 — reported to the client, not swallowed
        _set_status(repo_id, status="error", message=f"Indexing failed: {exc}")
