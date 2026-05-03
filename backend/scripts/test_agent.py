"""End-to-end agent smoke test.

Inserts a user into SQLite, runs the LangGraph agent, prints the resulting state.
Requires GROQ_API_KEY in backend/.env.

Run: uv run python scripts/test_agent.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from pprint import pprint

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import run_agent  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402


def _ensure_user(db, name: str, vibe: str, interests: list[str]) -> User:
    existing = db.query(User).filter(User.name == name).one_or_none()
    if existing:
        return existing
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        vibe_text=vibe,
        interests=", ".join(interests),
        vibe_analysis_json="{}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed two contrasting baseline users so the matcher has someone to find.
        _ensure_user(
            db, "Maya",
            "Late-night coder, lo-fi at 2am, building weird side projects, "
            "loves talking about tools and taste.",
            ["coding", "lo-fi", "ramen", "side projects"],
        )
        _ensure_user(
            db, "Priya",
            "Trail runner, stoicism podcasts, early mornings, fitness journaling.",
            ["running", "stoicism", "fitness", "podcasts"],
        )

        # Hero user we'll run the agent for.
        hero = _ensure_user(
            db, "Karthik",
            "ML researcher, runs cooking experiments on weekends, listens to "
            "classical music, takes long walks to think.",
            ["ml", "cooking", "classical music", "walks"],
        )
        # Re-insert their vibes via the agent path for the two seeds, so they're
        # in the vector store too.
        for seed_name in ("Maya", "Priya"):
            seed = db.query(User).filter(User.name == seed_name).one()
            run_agent(seed.id, seed.name, seed.vibe_text, seed.interests_list())

        result = run_agent(hero.id, hero.name, hero.vibe_text, hero.interests_list())

        print("\n=== VIBE ANALYSIS ===")
        pprint(result.get("vibe_analysis"))
        print("\n=== MATCHES ===")
        for m in result.get("matches", []):
            print(f"  {m['name']:>10}  similarity={m['similarity_score']:.3f}")
            for ib in result.get("icebreakers", {}).get(m["user_id"], []):
                print(f"     • {ib}")

        # Persist hero's analysis to the row (this is what the API will do too).
        hero.vibe_analysis_json = json.dumps(result.get("vibe_analysis", {}))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
