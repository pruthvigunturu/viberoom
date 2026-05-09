"""HuggingFace sentence-transformers embeddings.

What's an "embedding"?
  A fixed-size vector of floats that captures the *meaning* of a piece of
  text. Two sentences with similar meaning have vectors that are close
  together in vector space (small cosine distance). That's what lets us
  do semantic matching ("find users with a similar vibe") instead of
  keyword matching.

Model: ``all-MiniLM-L6-v2``
  * Output size: 384 dimensions.
  * Size on disk: ~80MB.
  * Speed: very fast on CPU (we don't need a GPU for hackathon volumes).

Lazy loading:
  Loading the model takes a couple of seconds and ~200MB of RAM, so we
  defer it until the first ``embed_text`` call. The double-checked locking
  pattern below makes that safe in a multi-threaded server.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from sentence_transformers import SentenceTransformer

from .config import settings

log = logging.getLogger("viberoom.embeddings")

# Module-level cache so we only load the model once per process.
_model: Optional[SentenceTransformer] = None
_lock = threading.Lock()


def _get_model() -> SentenceTransformer:
    """Return the singleton model, loading it on first use.

    Double-checked locking: the outer ``if`` is the fast path (no lock
    contention once loaded). The inner ``if`` re-checks under the lock to
    avoid two threads each constructing a model on a race.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                log.info("Loading embedding model: %s", settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
                log.info("Embedding model ready (%d dim).", _model.get_sentence_embedding_dimension())
    return _model


def embed_text(text: str) -> list[float]:
    """Encode a single string into a 384-dim float vector.

    ``normalize_embeddings=True`` rescales each vector to unit length (L2
    norm = 1). With unit vectors, cosine similarity becomes a simple dot
    product — and ChromaDB's cosine distance becomes well-behaved in [0, 2].
    """
    vec = _get_model().encode(text, normalize_embeddings=True)
    # ``.tolist()`` converts numpy.ndarray → plain Python list, which is
    # what ChromaDB expects for its API.
    return vec.tolist()
