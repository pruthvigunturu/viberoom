"""SQLAlchemy ORM models — the "shape" of our database tables.

This file defines Python classes that mirror DB rows. SQLAlchemy translates
ORM operations (``db.add(user)``, ``db.query(User).filter(...)``) into SQL.

We keep the schema deliberately small: one ``users`` table that holds
everything we need to run the matching agent.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    """Generate a fresh primary key. UUIDs (vs auto-increment ints) make IDs
    safe to expose in URLs without leaking row counts or being guessable."""
    return str(uuid.uuid4())


def _now() -> datetime:
    """Always store timestamps in UTC. Convert to the user's timezone in the UI."""
    return datetime.now(timezone.utc)


class User(Base):
    """A single VibeRoom user — the only entity in our domain right now.

    Fields:
      * ``id``                  Stable opaque identifier (UUID4 string).
      * ``name``                Display name. Not unique on purpose — vibe matters more.
      * ``vibe_text``           The free-form paragraph the user typed.
      * ``interests``           CSV string of interests. Stored as text for simplicity;
                                if we needed to query by interest we'd normalize to
                                a separate table.
      * ``vibe_analysis_json``  JSON blob holding the LLM's structured analysis
                                (mood, energy_level, key_themes, summary). Cached
                                here so we don't re-call the LLM every page load.
      * ``created_at``          When this row was inserted.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    vibe_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Comma-separated values. ``interests_list()`` parses it back into a list.
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Cached LLM analysis. Default "{}" so json.loads never fails on fresh rows.
    vibe_analysis_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def interests_list(self) -> list[str]:
        """Return ``interests`` as a clean list of strings (CSV → list).

        Empty entries from things like "music, , coding" are dropped.
        """
        return [i.strip() for i in self.interests.split(",") if i.strip()]
