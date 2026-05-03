"""HuggingFace sentence-transformers embeddings.

Produces a 384-dimensional vector capturing the semantic meaning of free-form
vibe text, used downstream for cosine-similarity search in ChromaDB. The model
is lazy-loaded on first use because it's ~80MB and we don't want startup to block.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from sentence_transformers import SentenceTransformer

from .config import settings

log = logging.getLogger("viberoom.embeddings")

_model: Optional[SentenceTransformer] = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                log.info("Loading embedding model: %s", settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
                log.info("Embedding model ready (%d dim).", _model.get_sentence_embedding_dimension())
    return _model


def embed_text(text: str) -> list[float]:
    """Encode a single string into a 384-dim float vector."""
    vec = _get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()
