"""ChromaDB-backed vector store for user vibe embeddings.

What's a vector store?
  A database that indexes high-dimensional vectors and lets you ask
  "give me the K vectors closest to this query vector" very quickly.
  We use it to find users whose vibe embedding is closest to the
  current user's vibe embedding.

Why ChromaDB?
  * Pure Python, runs in-process — no extra service to operate.
  * Persists to disk under ``settings.chroma_persist_dir``.
  * Built-in cosine distance with HNSW (an approximate nearest-neighbour
    index that's fast and accurate enough for our scale).

Concept cheat-sheet:
  * **Collection**       Like a table. We have one: ``user_vibes``.
  * **id**               Stable identifier (we use the ``User.id`` UUID).
  * **embedding**        The 384-dim vector from ``embeddings.embed_text``.
  * **document**         The original text (handy for debugging).
  * **metadata**         Scalar key/value pairs travelling with each vector
                         (name, mood, ...). Chroma rejects nested values.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import chromadb

from .config import settings
from .embeddings import embed_text

log = logging.getLogger("viberoom.vector_store")

# One collection for the whole app. If we needed multiple "spaces" (e.g.
# separate per-event matching) we'd parameterise this.
COLLECTION = "user_vibes"

# Module-level singletons, lazily initialised so test code can override
# settings before the client connects.
_client: Optional[chromadb.PersistentClient] = None
_collection = None
_lock = threading.Lock()


def _get_collection():
    """Return the singleton Chroma collection, creating it on first use.

    ``hnsw:space=cosine`` configures the index to use cosine distance,
    which pairs naturally with our L2-normalised embeddings.
    """
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
    """Coerce metadata values into Chroma-acceptable scalars.

    Chroma metadata only accepts ``str | int | float | bool | None``.
    We turn lists into comma-joined strings (lossy but readable in logs)
    and fall back to ``str(...)`` for anything else.
    """
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
    """Insert (or update) a user's vibe vector in the store.

    ``upsert`` means: if ``user_id`` already exists, replace it. That makes
    this safe to call when a user resubmits their vibe — no duplicates.
    """
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
    """Return up to ``top_k`` users whose vibe is closest to ``query_text``.

    Each item is ``{"user_id", "similarity_score", "metadata"}``.

    Notes for the curious:
      * Chroma's ``where`` clause for excluding IDs is awkward, so we
        over-fetch by a few extra rows and filter in Python instead.
      * Cosine distance from Chroma is in [0, 2]. We convert to a friendly
        similarity score in [0, 1] with ``max(0, 1 - distance)`` so the UI
        can render "73% match"-style numbers.
    """
    coll = _get_collection()
    embedding = embed_text(query_text)

    # Pad fetch size so we can still return ``top_k`` after filtering.
    fetch_k = top_k + (len(exclude_ids) if exclude_ids else 0) + 1
    results = coll.query(
        query_embeddings=[embedding],
        n_results=fetch_k,
    )

    # Chroma returns parallel arrays nested one level deep (because the
    # API supports batching multiple queries). We're querying with one
    # embedding, so we always read the [0]th row.
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    out: list[dict] = []
    excluded = set(exclude_ids or [])
    for uid, dist, meta in zip(ids, distances, metadatas):
        if uid in excluded:
            continue
        # Convert cosine *distance* → cosine *similarity*, clamped to [0, 1].
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        out.append({"user_id": uid, "similarity_score": similarity, "metadata": meta or {}})
        if len(out) >= top_k:
            break
    return out


def reset() -> None:
    """Drop and recreate the collection. Test-only — never call in prod."""
    global _client, _collection
    coll = _get_collection()
    assert _client is not None
    _client.delete_collection(COLLECTION)
    _collection = None
    _get_collection()
