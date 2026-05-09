"""Pydantic schemas — the "shape" of data crossing the API boundary.

Why we have BOTH SQLAlchemy models (in ``models.py``) AND Pydantic schemas:

  * SQLAlchemy models describe the database. They include private/internal
    fields (e.g. raw ``vibe_analysis_json`` string).
  * Pydantic schemas describe the JSON the API accepts and returns. They
    validate input from the client and shape the output for the UI.

Keeping them separate means we can change the database schema without
breaking the API contract (and vice versa).
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Body of ``POST /users`` — what the client sends to create a user."""

    # Field(...) lets us declare validation rules. FastAPI returns a clear
    # 422 error automatically if these fail.
    name: str = Field(min_length=1, max_length=120)
    vibe_text: str = Field(min_length=1, max_length=4000)
    interests: list[str] = Field(default_factory=list)


class UserOut(BaseModel):
    """User as returned by the API. Note ``interests`` is a list (not CSV)."""

    id: str
    name: str
    vibe_text: str
    interests: list[str]
    created_at: datetime

    # ``from_attributes=True`` lets Pydantic populate this model directly
    # from a SQLAlchemy ORM object (reading attributes vs. dict keys).
    model_config = {"from_attributes": True}


class VibeAnalysis(BaseModel):
    """Structured output from the LLM's vibe-analysis step.

    Defaults are intentionally permissive — if the LLM returns garbage we
    still want a well-formed response rather than a 500.
    """

    mood: str = ""
    # ``ge`` / ``le`` clamp the LLM's output to a sensible 1–10 range.
    energy_level: int = Field(default=5, ge=1, le=10)
    key_themes: list[str] = Field(default_factory=list)
    summary: str = ""


class MatchOut(BaseModel):
    """One suggested match: another user, plus the score and AI extras."""

    user: UserOut
    similarity_score: float  # cosine-similarity in [0, 1]
    vibe_analysis: VibeAnalysis | None = None
    icebreakers: list[str] = Field(default_factory=list)


class AgentResultOut(BaseModel):
    """The full payload returned after the agent runs end-to-end."""

    user: UserOut
    vibe_analysis: VibeAnalysis
    matches: list[MatchOut]
    # ``raw_state`` is reserved for debugging/observability — surface the
    # internal LangGraph state to the UI when we want to inspect a run.
    raw_state: dict[str, Any] | None = None
