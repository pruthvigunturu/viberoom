"""Seed the demo with 8 diverse fictional users.

Hits the running API directly so it goes through the same agent pipeline as
real signups. Run AFTER the backend is up, e.g.:

  uv run python scripts/seed.py
  # or, if the API is in Docker:
  API_URL=http://localhost:8000 uv run python scripts/seed.py
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
import json

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

SEED_USERS = [
    {
        "name": "Maya",
        "vibe_text": "Late-night coder, lo-fi at 2am, building weird side projects, "
                     "the kind that nobody asked for but make me smile.",
        "interests": ["coding", "lo-fi", "ramen", "side projects", "indie tools"],
    },
    {
        "name": "Arjun",
        "vibe_text": "Designer who lives in coffee shops, always sketching, "
                     "loves long conversations about typography and visual culture.",
        "interests": ["design", "coffee", "typography", "sketching", "branding"],
    },
    {
        "name": "Priya",
        "vibe_text": "Trail runner, podcasts on stoicism while I move, "
                     "early mornings only, building a calmer version of myself.",
        "interests": ["running", "stoicism", "fitness", "podcasts", "mornings"],
    },
    {
        "name": "Dev",
        "vibe_text": "Foodie traveler. Street food, languages, photography, jazz. "
                     "I'd rather get lost in a market than visit a museum.",
        "interests": ["travel", "food", "photography", "jazz", "languages"],
    },
    {
        "name": "Anika",
        "vibe_text": "Climate-tech founder, obsessed with systems thinking, "
                     "drink tea ceremonially, read nonfiction at the speed of light.",
        "interests": ["climate", "systems thinking", "tea", "nonfiction", "founder life"],
    },
    {
        "name": "Rohan",
        "vibe_text": "Quiet gamer with a soft spot for indie games, weekend hikes, "
                     "and sci-fi novels with weird premises.",
        "interests": ["indie games", "hiking", "sci-fi", "writing", "introvert"],
    },
    {
        "name": "Sara",
        "vibe_text": "Musician and songwriter. Vinyl collector. Late-night philosophy "
                     "chats are my favorite genre of conversation.",
        "interests": ["music", "songwriting", "vinyl", "philosophy", "late nights"],
    },
    {
        "name": "Karthik",
        "vibe_text": "ML researcher who runs cooking experiments on weekends, "
                     "listens to classical, takes long walks to think out loud.",
        "interests": ["ml", "cooking", "classical music", "walks", "papers"],
    },
]


def _post_user(payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_URL}/users",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _wait_for_api(timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError):
            pass
        time.sleep(1)
    raise RuntimeError(f"API not reachable at {API_URL} after {timeout_s}s")


def main() -> None:
    print(f"Seeding via {API_URL}")
    _wait_for_api()
    for u in SEED_USERS:
        print(f"  → {u['name']}…", end=" ", flush=True)
        try:
            result = _post_user(u)
            mood = result.get("vibe_analysis", {}).get("mood", "?")
            n_matches = len(result.get("matches", []))
            print(f"ok (mood={mood!r}, matches={n_matches})")
        except urllib.error.HTTPError as e:
            print(f"FAIL {e.code}: {e.read().decode()}")
            sys.exit(1)

    # final count
    with urllib.request.urlopen(f"{API_URL}/users") as r:
        users = json.loads(r.read().decode())
    print(f"\nTotal users: {len(users)}")


if __name__ == "__main__":
    main()
