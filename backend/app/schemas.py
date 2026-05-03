from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    vibe_text: str = Field(min_length=1, max_length=4000)
    interests: list[str] = Field(default_factory=list)


class UserOut(BaseModel):
    id: str
    name: str
    vibe_text: str
    interests: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VibeAnalysis(BaseModel):
    mood: str = ""
    energy_level: int = Field(default=5, ge=1, le=10)
    key_themes: list[str] = Field(default_factory=list)
    summary: str = ""


class MatchOut(BaseModel):
    user: UserOut
    similarity_score: float
    vibe_analysis: VibeAnalysis | None = None
    icebreakers: list[str] = Field(default_factory=list)


class AgentResultOut(BaseModel):
    user: UserOut
    vibe_analysis: VibeAnalysis
    matches: list[MatchOut]
    raw_state: dict[str, Any] | None = None
