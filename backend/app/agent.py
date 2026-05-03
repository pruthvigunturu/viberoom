"""VibeRoom LangGraph agent.

A 4-node pipeline that turns a user's free-form vibe into matches and
personalized icebreakers. Each node is independently testable, observable,
and swappable — that's why it's a graph instead of a chain of inline calls.

  START → analyze_vibe → embed_and_store → find_matches → generate_icebreakers → END

State flows through a TypedDict, the icebreaker calls fan out via asyncio.gather
so latency is bounded by the slowest match-LLM call rather than their sum.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import User
from .vector_store import add_user as vs_add_user
from .vector_store import find_similar

log = logging.getLogger("viberoom.agent")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    user_id: str
    name: str
    vibe_text: str
    interests: list[str]
    vibe_analysis: dict
    embedding_text: str
    matches: list[dict]
    icebreakers: dict[str, list[str]]


# ---------------------------------------------------------------------------
# LLM wiring
# ---------------------------------------------------------------------------
def _llm(temperature: float = 0.4, json_mode: bool = True) -> ChatGroq:
    kwargs: dict[str, Any] = {
        "model": settings.groq_model,
        "api_key": settings.groq_api_key,
        "temperature": temperature,
        "max_retries": 2,
    }
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatGroq(**kwargs)


_json_parser = JsonOutputParser()


def _safe_parse_json(content: str, fallback: dict) -> dict:
    """Parse JSON from an LLM message, falling back to defaults on bad output."""
    try:
        return _json_parser.parse(content)
    except (OutputParserException, ValueError, json.JSONDecodeError) as e:
        log.warning("JSON parse failed (%s); raw=%r", e, content[:200])
        return fallback


# ---------------------------------------------------------------------------
# Node 1 — analyze_vibe
# ---------------------------------------------------------------------------
ANALYZE_SYSTEM = (
    "You are a vibe analyst. Given someone's free-form description of their "
    "current mood and a list of interests, extract a structured profile. "
    "Output STRICT JSON only — no prose, no markdown fences."
)

ANALYZE_TEMPLATE = """User vibe: {vibe_text}
Interests: {interests}

Return JSON with EXACTLY these keys:
  "mood":         a 1-3 word descriptor (e.g. "focused", "playful", "restless")
  "energy_level": integer 1-10
  "key_themes":   list of 3-5 short topical themes
  "summary":      one-sentence summary of who this person is right now

JSON only. No backticks. No explanation."""


def analyze_vibe(state: AgentState) -> AgentState:
    llm = _llm(temperature=0.3)
    prompt = ANALYZE_TEMPLATE.format(
        vibe_text=state["vibe_text"],
        interests=", ".join(state.get("interests", [])) or "(none provided)",
    )
    try:
        resp = llm.invoke([SystemMessage(content=ANALYZE_SYSTEM), HumanMessage(content=prompt)])
        analysis = _safe_parse_json(
            resp.content,
            fallback={"mood": "curious", "energy_level": 5, "key_themes": [], "summary": state["vibe_text"][:120]},
        )
    except Exception as e:  # network, auth, rate limit
        log.warning("analyze_vibe LLM call failed: %s", e)
        analysis = {"mood": "curious", "energy_level": 5, "key_themes": [], "summary": state["vibe_text"][:120]}

    # Normalize types so downstream nodes don't have to defend against the LLM
    analysis.setdefault("mood", "curious")
    try:
        analysis["energy_level"] = int(analysis.get("energy_level", 5))
    except (TypeError, ValueError):
        analysis["energy_level"] = 5
    if not isinstance(analysis.get("key_themes"), list):
        analysis["key_themes"] = []
    analysis.setdefault("summary", state["vibe_text"][:120])

    return {"vibe_analysis": analysis}


# ---------------------------------------------------------------------------
# Node 2 — embed_and_store
# ---------------------------------------------------------------------------
def embed_and_store(state: AgentState) -> AgentState:
    interests = state.get("interests", [])
    themes = state.get("vibe_analysis", {}).get("key_themes", [])
    embedding_text = (
        f"{state['vibe_text']}, "
        f"interests: {', '.join(interests)}, "
        f"themes: {', '.join(themes)}"
    )
    metadata = {
        "name": state["name"],
        "mood": state.get("vibe_analysis", {}).get("mood", ""),
        "energy_level": state.get("vibe_analysis", {}).get("energy_level", 5),
        "summary": state.get("vibe_analysis", {}).get("summary", ""),
    }
    vs_add_user(state["user_id"], embedding_text, metadata)
    return {"embedding_text": embedding_text}


# ---------------------------------------------------------------------------
# Node 3 — find_matches
# ---------------------------------------------------------------------------
def find_matches(state: AgentState) -> AgentState:
    # Over-fetch so we have headroom to drop same-name duplicates (e.g. a user
    # who submits the form twice with the same name shouldn't see themselves).
    raw = find_similar(
        query_text=state["embedding_text"],
        top_k=10,
        exclude_ids=[state["user_id"]],
    )

    own_name = (state.get("name") or "").strip().casefold()

    db: Session = SessionLocal()
    try:
        matches: list[dict] = []
        for m in raw:
            row = db.query(User).filter(User.id == m["user_id"]).one_or_none()
            if row is None:
                continue
            if own_name and row.name.strip().casefold() == own_name:
                continue
            try:
                analysis = json.loads(row.vibe_analysis_json or "{}")
            except json.JSONDecodeError:
                analysis = {}
            matches.append({
                "user_id": row.id,
                "name": row.name,
                "vibe_text": row.vibe_text,
                "interests": row.interests_list(),
                "similarity_score": m["similarity_score"],
                "vibe_analysis": analysis,
            })
            if len(matches) >= 3:
                break
    finally:
        db.close()

    return {"matches": matches}


# ---------------------------------------------------------------------------
# Node 4 — generate_icebreakers (parallelized)
# ---------------------------------------------------------------------------
ICEBREAKER_SYSTEM = (
    "You write warm, specific icebreaker questions for a social app. "
    "Return STRICT JSON only — no prose, no markdown fences."
)

ICEBREAKER_TEMPLATE = """User A: {name_a}
User A vibe: {vibe_a}
User A interests: {interests_a}

User B: {name_b}
User B vibe: {vibe_b}
User B interests: {interests_b}

Generate EXACTLY 2 icebreaker questions User A could ask User B to start a great conversation.
They should reference shared interests or complementary energy — specific, not generic.

Return JSON:
  {{"icebreakers": ["question 1", "question 2"]}}

JSON only."""


async def _icebreaker_for_match(llm: ChatGroq, state: AgentState, match: dict) -> tuple[str, list[str]]:
    prompt = ICEBREAKER_TEMPLATE.format(
        name_a=state["name"],
        vibe_a=state["vibe_text"],
        interests_a=", ".join(state.get("interests", [])) or "(none)",
        name_b=match["name"],
        vibe_b=match["vibe_text"],
        interests_b=", ".join(match.get("interests", [])) or "(none)",
    )
    try:
        resp = await llm.ainvoke([SystemMessage(content=ICEBREAKER_SYSTEM), HumanMessage(content=prompt)])
        parsed = _safe_parse_json(resp.content, fallback={"icebreakers": []})
        breakers = parsed.get("icebreakers") or []
        if not isinstance(breakers, list):
            breakers = []
        breakers = [str(b) for b in breakers][:2]
        while len(breakers) < 2:
            breakers.append(f"What's the latest thing you've been into, {match['name']}?")
    except Exception as e:
        log.warning("icebreaker LLM call failed for %s: %s", match["user_id"], e)
        breakers = [
            f"Hey {match['name']}, what's keeping you busy this week?",
            f"What got you into {(match.get('interests') or ['this'])[0]}?",
        ]
    return match["user_id"], breakers


async def _generate_icebreakers_async(state: AgentState) -> dict[str, list[str]]:
    matches = state.get("matches", [])
    if not matches:
        return {}
    llm = _llm(temperature=0.7)
    results = await asyncio.gather(*[_icebreaker_for_match(llm, state, m) for m in matches])
    return {uid: ibs for uid, ibs in results}


def generate_icebreakers(state: AgentState) -> AgentState:
    icebreakers = asyncio.run(_generate_icebreakers_async(state))
    return {"icebreakers": icebreakers}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("analyze_vibe", analyze_vibe)
    graph.add_node("embed_and_store", embed_and_store)
    graph.add_node("find_matches", find_matches)
    graph.add_node("generate_icebreakers", generate_icebreakers)

    graph.add_edge(START, "analyze_vibe")
    graph.add_edge("analyze_vibe", "embed_and_store")
    graph.add_edge("embed_and_store", "find_matches")
    graph.add_edge("find_matches", "generate_icebreakers")
    graph.add_edge("generate_icebreakers", END)

    return graph.compile()


agent_graph = _build_graph()


def run_agent(user_id: str, name: str, vibe_text: str, interests: list[str]) -> AgentState:
    initial: AgentState = {
        "user_id": user_id,
        "name": name,
        "vibe_text": vibe_text,
        "interests": interests,
    }
    return agent_graph.invoke(initial)


def run_match_only(user_id: str, name: str, vibe_text: str, interests: list[str], embedding_text: str) -> AgentState:
    """Skip analyze + embed_and_store; user is already in the vector store."""
    state: AgentState = {
        "user_id": user_id,
        "name": name,
        "vibe_text": vibe_text,
        "interests": interests,
        "embedding_text": embedding_text,
    }
    state.update(find_matches(state))
    state.update(generate_icebreakers(state))
    return state
