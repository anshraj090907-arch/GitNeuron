"""
Embedding model wrapper.

Local, free, and deterministic by default (Sentence-Transformers), so
the whole pipeline works offline with no API key. The model name is
configurable, so a hosted embedding API can be swapped in without
touching any other module.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _model().encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
