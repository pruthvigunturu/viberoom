"""ChromaDB-backed vector store for user vibe embeddings.

Single collection ("user_vibes") with cosine-distance metric. We convert
distance to similarity with `1 - distance`, clamped to [0, 1].
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import chromadb

from .config import settings
from .embeddings import embed_text

log = logging.getLogger("viberoom.vector_store")

COLLECTION = "user_vibes"

_client: Optional[chromadb.PersistentClient] = None
_collection = None
_lock = threading.Lock()


def _get_collection():
    global _client, _collection
    if _collection is None:
        with _lock:
            if _collection is None:
                _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
                _collection = _client.get_or_create_collection(
                    name=COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
                log.info("Chroma collection ready: %s", COLLECTION)
    return _collection


def _flatten_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Chroma metadata only accepts scalars. Coerce lists to comma-strings."""
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = ", ".join(str(x) for x in v)
        else:
            out[k] = str(v)
    return out


def add_user(user_id: str, text: str, metadata: dict[str, Any]) -> None:
    coll = _get_collection()
    embedding = embed_text(text)
    coll.upsert(
        ids=[user_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[_flatten_metadata(metadata)],
    )


def find_similar(
    query_text: str,
    top_k: int = 3,
    exclude_ids: list[str] | None = None,
) -> list[dict]:
    coll = _get_collection()
    embedding = embed_text(query_text)

    # Chroma `where` over IDs is awkward; over-fetch and filter in Python instead.
    fetch_k = top_k + (len(exclude_ids) if exclude_ids else 0) + 1
    results = coll.query(
        query_embeddings=[embedding],
        n_results=fetch_k,
    )

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    out: list[dict] = []
    excluded = set(exclude_ids or [])
    for uid, dist, meta in zip(ids, distances, metadatas):
        if uid in excluded:
            continue
        # cosine distance ∈ [0, 2] under Chroma; similarity = 1 - dist clamped to [0, 1]
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        out.append({"user_id": uid, "similarity_score": similarity, "metadata": meta or {}})
        if len(out) >= top_k:
            break
    return out


def reset() -> None:
    """Drop and recreate the collection. Test-only."""
    global _client, _collection
    coll = _get_collection()
    assert _client is not None
    _client.delete_collection(COLLECTION)
    _collection = None
    _get_collection()
