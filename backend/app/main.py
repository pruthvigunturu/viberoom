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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("viberoom")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    log.info("VibeRoom API up.")
    log.info("  DB:       %s", settings.database_url)
    log.info("  Chroma:   %s", settings.chroma_persist_dir)
    log.info("  Embed:    %s", settings.embedding_model)
    log.info("  LLM:      %s (%s)", settings.groq_model, "key set" if settings.groq_api_key else "NO KEY")
    log.info("  CORS:     %s", settings.cors_origins_list)
    yield


app = FastAPI(
    title="VibeRoom API",
    description="AI-powered social engagement platform — vibe matching with LangGraph.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        vibe_text=user.vibe_text,
        interests=user.interests_list(),
        created_at=user.created_at,
    )


_VA_KEYS = ("mood", "energy_level", "key_themes", "summary")


def _safe_vibe_analysis(data: dict | None) -> VibeAnalysis:
    """Build a VibeAnalysis from a dict, swallowing schema violations.

    LLM output occasionally drifts (e.g. energy_level=15); we'd rather degrade
    to defaults than 500 the whole request.
    """
    if not data:
        return VibeAnalysis()
    try:
        return VibeAnalysis(**{k: data[k] for k in _VA_KEYS if k in data})
    except Exception:
        return VibeAnalysis()


def _analysis_from_row(row: User) -> VibeAnalysis:
    try:
        data = json.loads(row.vibe_analysis_json or "{}")
    except json.JSONDecodeError:
        data = {}
    return _safe_vibe_analysis(data)


def _build_result(user: User, agent_state: dict, db: Session) -> AgentResultOut:
    matches_out: list[MatchOut] = []
    icebreakers = agent_state.get("icebreakers", {})
    for m in agent_state.get("matches", []):
        match_user = db.query(User).filter(User.id == m["user_id"]).one_or_none()
        if match_user is None:
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
    return {"status": "ok"}


@app.post("/users", response_model=AgentResultOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> AgentResultOut:
    user = User(
        name=payload.name.strip(),
        vibe_text=payload.vibe_text.strip(),
        interests=", ".join(i.strip() for i in payload.interests if i.strip()),
        vibe_analysis_json="{}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    state = run_agent(user.id, user.name, user.vibe_text, user.interests_list())

    user.vibe_analysis_json = json.dumps(state.get("vibe_analysis") or {})
    db.commit()
    db.refresh(user)

    return _build_result(user, state, db)


@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_to_out(u) for u in users]


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)) -> UserOut:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_out(user)


@app.get("/users/{user_id}/matches", response_model=AgentResultOut)
def get_matches(user_id: str, db: Session = Depends(get_db)) -> AgentResultOut:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    interests = user.interests_list()
    try:
        analysis = json.loads(user.vibe_analysis_json or "{}")
    except json.JSONDecodeError:
        analysis = {}
    themes = analysis.get("key_themes") or []
    embedding_text = (
        f"{user.vibe_text}, "
        f"interests: {', '.join(interests)}, "
        f"themes: {', '.join(themes)}"
    )

    state = run_match_only(user.id, user.name, user.vibe_text, interests, embedding_text)
    state["vibe_analysis"] = analysis  # keep prior analysis on the response
    return _build_result(user, state, db)


@app.get("/users/{user_id}/agent-trace", response_model=VibeAnalysis)
def get_agent_trace(user_id: str, db: Session = Depends(get_db)) -> VibeAnalysis:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _analysis_from_row(user)
