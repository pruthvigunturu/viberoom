"""FastAPI entry-point — wires HTTP routes to the agent + database.

Request lifecycle (the 30-second tour):

    Browser → POST /users → ``create_user``
         1. Persist a User row in SQLite via SQLAlchemy.
         2. Run the full LangGraph agent (analyse / embed / match / icebreaker).
         3. Cache the vibe analysis on the row so future calls are fast.
         4. Return ``AgentResultOut`` JSON to the frontend.

    Browser → GET /users/{id}/matches → ``get_matches``
         1. Load cached analysis from the DB (skip the LLM call).
         2. Run only the matching+icebreaker portion of the agent.
         3. Return fresh matches.

This file deliberately stays thin: route handlers do orchestration, business
logic lives in ``agent.py``, ``vector_store.py`` and the SQLAlchemy models.
"""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .agent import run_agent, run_match_only
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import User
from .schemas import (
    AgentResultOut,
    MatchOut,
    UserCreate,
    UserOut,
    VibeAnalysis,
)

# Configure root logging exactly once. The format includes a timestamp and
# logger name, which makes it easy to grep production logs by component.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("viberoom")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs once on startup, then again (after the ``yield``) on shutdown.

    We use it to:
      * Auto-create the SQL tables on first run (fine for a hackathon — use
        Alembic migrations for a real product).
      * Print a one-liner summary of the active configuration so the logs
        immediately show whether secrets/env vars are wired up.
    """
    Base.metadata.create_all(bind=engine)
    log.info("VibeRoom API up.")
    log.info("  DB:       %s", settings.database_url)
    log.info("  Chroma:   %s", settings.chroma_persist_dir)
    log.info("  Embed:    %s", settings.embedding_model)
    log.info("  LLM:      %s (%s)", settings.groq_model, "key set" if settings.groq_api_key else "NO KEY")
    log.info("  CORS:     %s", settings.cors_origins_list)
    yield
    # (no cleanup needed — engine pool closes itself on process exit)


# The FastAPI application object. Imported by uvicorn as ``app.main:app``.
app = FastAPI(
    title="VibeRoom API",
    description="AI-powered social engagement platform — vibe matching with LangGraph.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS lets the browser frontend (different origin) talk to this API.
# In production we lock ``allow_origins`` down to the deployed UI URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers — small pure functions that translate between DB rows / agent
# state / API response models. Keeping these out of the route handlers
# makes the routes read like a high-level recipe.
# ---------------------------------------------------------------------------
def _user_to_out(user: User) -> UserOut:
    """Convert a SQLAlchemy ``User`` row → public ``UserOut`` schema."""
    return UserOut(
        id=user.id,
        name=user.name,
        vibe_text=user.vibe_text,
        interests=user.interests_list(),
        created_at=user.created_at,
    )


# Whitelist of keys we copy into ``VibeAnalysis``. Anything else from the
# LLM is ignored — defends against the model adding stray keys.
_VA_KEYS = ("mood", "energy_level", "key_themes", "summary")


def _safe_vibe_analysis(data: dict | None) -> VibeAnalysis:
    """Build a VibeAnalysis from a dict, swallowing schema violations.

    LLM output occasionally drifts (e.g. energy_level=15); we'd rather degrade
    to defaults than 500 the whole request. Pydantic raises on out-of-range
    values, so we catch broadly and return an empty default object.
    """
    if not data:
        return VibeAnalysis()
    try:
        return VibeAnalysis(**{k: data[k] for k in _VA_KEYS if k in data})
    except Exception:
        return VibeAnalysis()


def _analysis_from_row(row: User) -> VibeAnalysis:
    """Decode the JSON blob stored on the ``users`` row into a VibeAnalysis."""
    try:
        data = json.loads(row.vibe_analysis_json or "{}")
    except json.JSONDecodeError:
        # Should never happen, but if a row got corrupted we just show defaults.
        data = {}
    return _safe_vibe_analysis(data)


def _build_result(user: User, agent_state: dict, db: Session) -> AgentResultOut:
    """Assemble the full ``AgentResultOut`` payload returned to the UI.

    The agent state stores matches as plain dicts with just IDs — here we
    look up the corresponding ``User`` rows so the response includes
    everything the frontend needs to render a card.
    """
    matches_out: list[MatchOut] = []
    icebreakers = agent_state.get("icebreakers", {})
    for m in agent_state.get("matches", []):
        match_user = db.query(User).filter(User.id == m["user_id"]).one_or_none()
        if match_user is None:
            # Vector store knew about this id but the SQL row is gone.
            # Skip silently — the frontend just sees fewer matches.
            continue
        matches_out.append(MatchOut(
            user=_user_to_out(match_user),
            similarity_score=float(m["similarity_score"]),
            vibe_analysis=_safe_vibe_analysis(m.get("vibe_analysis")),
            icebreakers=icebreakers.get(m["user_id"], []),
        ))

    return AgentResultOut(
        user=_user_to_out(user),
        vibe_analysis=_safe_vibe_analysis(agent_state.get("vibe_analysis")),
        matches=matches_out,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    """Cheap probe used by Fly.io / load balancers to check liveness."""
    return {"status": "ok"}


@app.post("/users", response_model=AgentResultOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> AgentResultOut:
    """Create a user and run the full agent pipeline immediately.

    We do the agent run *inline* instead of in a background task so the
    UI can show the matches on the very next page — simpler UX, at the
    cost of a few seconds of latency on the first POST.
    """
    # Persist the row first so the agent has a stable user_id to use as
    # both the SQL primary key and the Chroma vector id.
    user = User(
        name=payload.name.strip(),
        vibe_text=payload.vibe_text.strip(),
        # Re-join the cleaned interest list into a CSV string for storage.
        interests=", ".join(i.strip() for i in payload.interests if i.strip()),
        vibe_analysis_json="{}",  # filled in below after the agent runs
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # populates server-side defaults like ``created_at``

    # Run the full graph: analyse → embed/store → match → icebreakers.
    state = run_agent(user.id, user.name, user.vibe_text, user.interests_list())

    # Cache the LLM analysis on the row so subsequent calls don't re-spend it.
    user.vibe_analysis_json = json.dumps(state.get("vibe_analysis") or {})
    db.commit()
    db.refresh(user)

    return _build_result(user, state, db)


@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    """List every user, newest first. Useful for the admin/debug view."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_to_out(u) for u in users]


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)) -> UserOut:
    """Fetch a single user by id, or 404."""
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_out(user)


@app.get("/users/{user_id}/matches", response_model=AgentResultOut)
def get_matches(user_id: str, db: Session = Depends(get_db)) -> AgentResultOut:
    """Re-run JUST matching + icebreakers for an existing user.

    This is the "refresh" button on the matches page. Skipping the
    analysis + embedding nodes saves an LLM call and the embedding model's
    GPU/CPU work.
    """
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    interests = user.interests_list()
    try:
        analysis = json.loads(user.vibe_analysis_json or "{}")
    except json.JSONDecodeError:
        analysis = {}
    themes = analysis.get("key_themes") or []

    # Reconstruct the same embedding text format used in ``embed_and_store``
    # so search results stay consistent between the create flow and refresh.
    embedding_text = (
        f"{user.vibe_text}, "
        f"interests: {', '.join(interests)}, "
        f"themes: {', '.join(themes)}"
    )

    state = run_match_only(user.id, user.name, user.vibe_text, interests, embedding_text)
    # Inject the cached analysis so the response payload is shaped identically
    # to the one returned by POST /users.
    state["vibe_analysis"] = analysis
    return _build_result(user, state, db)


@app.get("/users/{user_id}/agent-trace", response_model=VibeAnalysis)
def get_agent_trace(user_id: str, db: Session = Depends(get_db)) -> VibeAnalysis:
    """Return just the cached vibe analysis. Mostly for debugging / tooling."""
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _analysis_from_row(user)
