"""
Vector storage, backed by ChromaDB (persistent, local, one collection
per indexed repository). Swappable for FAISS or a hosted store behind
the same four functions without touching the retrieval or indexing
code that calls them.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib

import chromadb

from app.config import get_settings
from app.core.chunking import Chunk


@lru_cache
def _client():
    settings = get_settings()
    return chromadb.PersistentClient(path=str(settings.index_dir))


def _collection(repo_id: str):
    return _client().get_or_create_collection(
        name=f"repo_{repo_id}",
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(repo_id: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        return
    col = _collection(repo_id)
    ids = [
        f"{c.file_path}:{c.start_line}-{c.end_line}:{hashlib.sha1(c.text.encode()).hexdigest()[:8]}"
        for c in chunks
    ]
    metadatas = [
        {
            "file_path": c.file_path,
            "language": c.language,
            "start_line": c.start_line,
            "end_line": c.end_line,
        }
        for c in chunks
    ]
    documents = [c.text for c in chunks]
    # Chroma batches internally but has an add-size ceiling; stay well under it.
    BATCH = 256
    for i in range(0, len(ids), BATCH):
        col.upsert(
            ids=ids[i:i + BATCH],
            embeddings=embeddings[i:i + BATCH],
            metadatas=metadatas[i:i + BATCH],
            documents=documents[i:i + BATCH],
        )


def query(repo_id: str, query_embedding: list[float], top_k: int) -> list[dict]:
    col = _collection(repo_id)
    if col.count() == 0:
        return []
    result = col.query(query_embeddings=[query_embedding], n_results=min(top_k, col.count()))

    hits = []
    for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({
            "text": doc,
            "file_path": meta["file_path"],
            "language": meta["language"],
            "start_line": meta["start_line"],
            "end_line": meta["end_line"],
            "score": 1 - dist,  # cosine distance -> similarity
        })
    return hits


def collection_count(repo_id: str) -> int:
    try:
        return _collection(repo_id).count()
    except Exception:
        return 0


def delete_repo(repo_id: str) -> None:
    try:
        _client().delete_collection(f"repo_{repo_id}")
    except Exception:
        pass
