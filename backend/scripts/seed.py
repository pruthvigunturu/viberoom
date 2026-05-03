"""Seed the demo with 8 diverse fictional users.

Hits the running API directly so it goes through the same agent pipeline as
real signups. Run AFTER the backend is up, e.g.:

  uv run python scripts/seed.py
  # or, if the API is in Docker:
  API_URL=http://localhost:8000 uv run python scripts/seed.py
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

SEED_USERS = [
    # Tech & builders
    {
        "name": "Maya",
        "vibe_text": "Late-night coder, lo-fi at 2am, building weird side projects, "
                     "the kind that nobody asked for but make me smile.",
        "interests": ["coding", "lo-fi", "ramen", "side projects", "indie tools"],
    },
    {
        "name": "Karthik",
        "vibe_text": "ML researcher who runs cooking experiments on weekends, "
                     "listens to classical, takes long walks to think out loud.",
        "interests": ["ml", "cooking", "classical music", "walks", "papers"],
    },
    {
        "name": "Anika",
        "vibe_text": "Climate-tech founder, obsessed with systems thinking, "
                     "drink tea ceremonially, read nonfiction at the speed of light.",
        "interests": ["climate", "systems thinking", "tea", "nonfiction", "founder life"],
    },
    {
        "name": "Vikram",
        "vibe_text": "Open source maintainer by night, payments engineer by day. "
                     "Spend my mornings doing pushups and reading old engineering blogs.",
        "interests": ["open source", "fintech", "calisthenics", "blogs", "rust"],
    },
    {
        "name": "Lena",
        "vibe_text": "iOS developer who paints watercolors on weekends. Believe craft "
                     "matters and that most software is way uglier than it needs to be.",
        "interests": ["ios", "swift", "watercolor", "design", "minimalism"],
    },

    # Design & creative
    {
        "name": "Arjun",
        "vibe_text": "Designer who lives in coffee shops, always sketching, "
                     "loves long conversations about typography and visual culture.",
        "interests": ["design", "coffee", "typography", "sketching", "branding"],
    },
    {
        "name": "Sara",
        "vibe_text": "Musician and songwriter. Vinyl collector. Late-night philosophy "
                     "chats are my favorite genre of conversation.",
        "interests": ["music", "songwriting", "vinyl", "philosophy", "late nights"],
    },
    {
        "name": "Theo",
        "vibe_text": "Indie filmmaker. Watch one Tarkovsky film a month. Currently "
                     "obsessed with how silence carries emotion in a scene.",
        "interests": ["film", "tarkovsky", "editing", "sound design", "scripts"],
    },
    {
        "name": "Imani",
        "vibe_text": "Photographer who travels to capture light at weird hours. "
                     "Carry one camera and one lens, refuse to bring anything else.",
        "interests": ["photography", "travel", "light", "minimalism", "film cameras"],
    },
    {
        "name": "Marco",
        "vibe_text": "Bartender turned mixologist who treats cocktails like edible essays. "
                     "Read history obsessively, particularly anything about empire and trade.",
        "interests": ["cocktails", "history", "writing", "old cookbooks", "fermentation"],
    },

    # Outdoors & body
    {
        "name": "Priya",
        "vibe_text": "Trail runner, podcasts on stoicism while I move, "
                     "early mornings only, building a calmer version of myself.",
        "interests": ["running", "stoicism", "fitness", "podcasts", "mornings"],
    },
    {
        "name": "Jonah",
        "vibe_text": "Climber, mostly bouldering. Spend hours figuring out a single move. "
                     "It's the closest thing I have to meditation.",
        "interests": ["bouldering", "climbing", "movement", "minimalist gear", "outdoors"],
    },
    {
        "name": "Mira",
        "vibe_text": "Yoga teacher and sometimes-poet. Believe the body holds memory "
                     "and that breath is more interesting than people give it credit for.",
        "interests": ["yoga", "poetry", "breathwork", "tea", "slow mornings"],
    },
    {
        "name": "Diego",
        "vibe_text": "Cyclist, road and gravel. Love a 5am ride before anyone else is awake. "
                     "Coffee, podcasts, and one weird tan line.",
        "interests": ["cycling", "endurance", "podcasts", "coffee", "gravel rides"],
    },
    {
        "name": "Aviva",
        "vibe_text": "Skater since I was 12. Now I write about board sports for a living. "
                     "Soft spot for analog watches and stickers on laptops.",
        "interests": ["skating", "writing", "watches", "music", "subcultures"],
    },

    # Travel, food, language
    {
        "name": "Dev",
        "vibe_text": "Foodie traveler. Street food, languages, photography, jazz. "
                     "I'd rather get lost in a market than visit a museum.",
        "interests": ["travel", "food", "photography", "jazz", "languages"],
    },
    {
        "name": "Yuki",
        "vibe_text": "Linguist who collects words that don't translate. Currently learning "
                     "Portuguese, third language since college. Cook a lot of noodles.",
        "interests": ["linguistics", "noodles", "languages", "literature", "podcasts"],
    },
    {
        "name": "Nadia",
        "vibe_text": "Food writer, ex-chef. Travel for unfamiliar markets. Believe "
                     "good rice is a love language.",
        "interests": ["food", "writing", "travel", "rice", "kitchens"],
    },

    # Mind & quiet types
    {
        "name": "Rohan",
        "vibe_text": "Quiet gamer with a soft spot for indie games, weekend hikes, "
                     "and sci-fi novels with weird premises.",
        "interests": ["indie games", "hiking", "sci-fi", "writing", "introvert"],
    },
    {
        "name": "Felix",
        "vibe_text": "Philosophy grad student, chess player, occasional bread baker. "
                     "Most at peace when the conversation gets weird at 2am.",
        "interests": ["philosophy", "chess", "baking", "essays", "long walks"],
    },
    {
        "name": "Hana",
        "vibe_text": "Astronomer-turned-data scientist. Spend weekends looking up at the sky "
                     "and weekdays looking down at notebooks. Both feel like the same activity.",
        "interests": ["astronomy", "data science", "stargazing", "notebooks", "tea"],
    },
    {
        "name": "Ezra",
        "vibe_text": "Lawyer who reads policy papers for fun and runs a small newsletter "
                     "about boring infrastructure. Coffee snob. Believe public goods deserve attention.",
        "interests": ["policy", "newsletters", "coffee", "civics", "infrastructure"],
    },

    # Music & nightlife
    {
        "name": "Kai",
        "vibe_text": "DJ and music producer. Live for that moment when a room moves together. "
                     "Off-decks, I read about acoustics and drink terrible energy drinks.",
        "interests": ["dj", "production", "acoustics", "nightlife", "synths"],
    },
    {
        "name": "Camille",
        "vibe_text": "Dancer and choreographer. Believe movement teaches you things words can't. "
                     "Currently obsessed with collaborations between dancers and AI.",
        "interests": ["dance", "choreography", "ai", "collaboration", "stretching"],
    },

    # Crafts & makers
    {
        "name": "Idris",
        "vibe_text": "Woodworker who fell into furniture making after burning out from finance. "
                     "Believe slow work is the best therapy. Drink black coffee. Read mysteries.",
        "interests": ["woodworking", "furniture", "mysteries", "coffee", "slow craft"],
    },
    {
        "name": "Beatrice",
        "vibe_text": "Knitter and pattern designer who quit consulting two years ago. "
                     "Run a tiny yarn shop. Cats. Audiobooks. No regrets.",
        "interests": ["knitting", "patterns", "audiobooks", "cats", "tea"],
    },

    # Healthcare / science
    {
        "name": "Tomás",
        "vibe_text": "Med student who runs a podcast about weird medical history. "
                     "Spend my breaks watching cooking videos and arguing about pasta shapes.",
        "interests": ["medicine", "podcasts", "history", "pasta", "cooking videos"],
    },
    {
        "name": "Saanvi",
        "vibe_text": "Neuroscience PhD looking at how attention shifts during creative work. "
                     "On weekends I try terrible pottery and read poetry out loud.",
        "interests": ["neuroscience", "attention", "pottery", "poetry", "creative process"],
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
    with urllib.request.urlopen(req, timeout=120, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode())


def _wait_for_api(timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    last_err: str | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_URL}/health", timeout=15, context=_SSL_CTX) as r:
                if r.status == 200:
                    return
                last_err = f"status={r.status}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(2)
    raise RuntimeError(f"API not reachable at {API_URL} after {timeout_s}s. Last error: {last_err}")


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
    with urllib.request.urlopen(f"{API_URL}/users", context=_SSL_CTX) as r:
        users = json.loads(r.read().decode())
    print(f"\nTotal users: {len(users)}")


if __name__ == "__main__":
    main()
