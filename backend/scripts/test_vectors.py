"""Smoke test for embeddings + ChromaDB.

Adds three users with distinct vibes, queries with a fourth, prints ranked matches.
Run: uv run python scripts/test_vectors.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.vector_store import add_user, find_similar  # noqa: E402

USERS = [
    ("u1", "Late-night coder, lo-fi music, ramen, side projects, weird ideas.",
     {"name": "Maya", "mood": "focused", "energy_level": 4}),
    ("u2", "Trail runner, stoicism podcasts, early mornings, fitness routines.",
     {"name": "Priya", "mood": "energized", "energy_level": 9}),
    ("u3", "Climate-tech founder, systems thinking, tea ceremonies, nonfiction.",
     {"name": "Anika", "mood": "driven", "energy_level": 7}),
]

QUERY = "I write code at 1am with lo-fi playing, building little tools nobody asked for."


def main() -> None:
    for uid, text, meta in USERS:
        add_user(uid, text, meta)
        print(f"  added {uid} ({meta['name']})")

    print(f"\nquery: {QUERY!r}\n")
    matches = find_similar(QUERY, top_k=3)
    for i, m in enumerate(matches, 1):
        print(f"  {i}. {m['user_id']} ({m['metadata'].get('name')}) "
              f"similarity={m['similarity_score']:.3f}")


if __name__ == "__main__":
    main()
