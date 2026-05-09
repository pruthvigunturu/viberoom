"""VibeRoom LangGraph agent — the brain of the app.

Big picture
===========
A user types a paragraph describing their vibe. We want to:
  1. Understand it (extract mood, energy, themes).
  2. Index it so other users can find them.
  3. Find the closest existing users.
  4. Generate personalized icebreakers for each match.

We model that as a 4-node *graph*::

    START → analyze_vibe → embed_and_store → find_matches → generate_icebreakers → END

Why a graph instead of a single function?
  * Each node is independently testable, observable, and swappable.
  * LangGraph gives us automatic state-passing, retries, and tracing.
  * If we later want branching (e.g. "skip matching for low-quality vibes")
    we add a conditional edge — no rewriting of the whole pipeline.

State flow
==========
A single ``AgentState`` (TypedDict) flows through every node. Each node
returns a *partial* state — the keys it produced — and LangGraph merges
that into the running state. Nodes never mutate the state in place.

Performance note
================
Icebreakers are generated in parallel via ``asyncio.gather``: with N matches,
total latency is bounded by the slowest single LLM call rather than N×.
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
# State — the shared "blackboard" every node reads from and writes to.
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    """The per-run state. ``total=False`` means every key is optional —
    nodes contribute keys progressively as the pipeline runs."""
    # Inputs (set when the run starts)
    user_id: str
    name: str
    vibe_text: str
    interests: list[str]

    # Set by ``analyze_vibe``
    vibe_analysis: dict

    # Set by ``embed_and_store``
    embedding_text: str

    # Set by ``find_matches``
    matches: list[dict]

    # Set by ``generate_icebreakers``: maps match user_id → list of questions
    icebreakers: dict[str, list[str]]


# ---------------------------------------------------------------------------
# LLM wiring — one helper to construct a configured ChatGroq client.
# ---------------------------------------------------------------------------
def _llm(temperature: float = 0.4, json_mode: bool = True) -> ChatGroq:
    """Build a ChatGroq client.

    Args:
        temperature: How "creative" the model is. Lower = more deterministic.
                     We use 0.3 for analysis (we want consistent JSON), and
                     0.7 for icebreakers (we want some variety).
        json_mode:   When True, ask the API to enforce strict JSON output.
                     This dramatically reduces parser failures.
    """
    kwargs: dict[str, Any] = {
        "model": settings.groq_model,
        "api_key": settings.groq_api_key,
        "temperature": temperature,
        "max_retries": 2,  # retry once on transient errors before giving up
    }
    if json_mode:
        # Groq honours OpenAI's ``response_format`` parameter for JSON mode.
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatGroq(**kwargs)


# Reuse one parser instance — it's stateless.
_json_parser = JsonOutputParser()


def _safe_parse_json(content: str, fallback: dict) -> dict:
    """Parse JSON from an LLM message, falling back to defaults on bad output.

    Even with JSON mode enabled the model occasionally emits malformed text
    (truncation, leading whitespace, ...). We log it and degrade gracefully
    rather than 500 the request.
    """
    try:
        return _json_parser.parse(content)
    except (OutputParserException, ValueError, json.JSONDecodeError) as e:
        log.warning("JSON parse failed (%s); raw=%r", e, content[:200])
        return fallback


# ---------------------------------------------------------------------------
# Node 1 — analyze_vibe
# Turn a free-form paragraph into a structured profile we can index/render.
# ---------------------------------------------------------------------------
ANALYZE_SYSTEM = (
    "You are a vibe analyst. Given someone's free-form description of their "
    "current mood and a list of interests, extract a structured profile. "
    "Output STRICT JSON only — no prose, no markdown fences."
)

# A user-message template. ``.format(...)`` interpolates per-call values.
ANALYZE_TEMPLATE = """User vibe: {vibe_text}
Interests: {interests}

Return JSON with EXACTLY these keys:
  "mood":         a 1-3 word descriptor (e.g. "focused", "playful", "restless")
  "energy_level": integer 1-10
  "key_themes":   list of 3-5 short topical themes
  "summary":      one-sentence summary of who this person is right now

JSON only. No backticks. No explanation."""


def analyze_vibe(state: AgentState) -> AgentState:
    """Call the LLM to produce ``state['vibe_analysis']``.

    Returns only the keys this node added — LangGraph merges that into
    the running state automatically.
    """
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
    except Exception as e:  # network, auth, rate limit, etc.
        log.warning("analyze_vibe LLM call failed: %s", e)
        analysis = {"mood": "curious", "energy_level": 5, "key_themes": [], "summary": state["vibe_text"][:120]}

    # Normalize types so downstream nodes don't have to defend against the LLM.
    # The model occasionally returns a string for energy_level or skips a key.
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
# Build the text we embed (vibe + interests + extracted themes), then upsert
# it into the vector store so future searches can find this user.
# ---------------------------------------------------------------------------
def embed_and_store(state: AgentState) -> AgentState:
    """Index this user in the vector DB.

    The embedded text concatenates the raw vibe with the structured
    interests and themes so that semantically related users — even if
    they used different wording — end up close in vector space.
    """
    interests = state.get("interests", [])
    themes = state.get("vibe_analysis", {}).get("key_themes", [])
    embedding_text = (
        f"{state['vibe_text']}, "
        f"interests: {', '.join(interests)}, "
        f"themes: {', '.join(themes)}"
    )
    # Metadata is optional but useful for debugging and "explain why this matched".
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
# Ask the vector store for nearest neighbours, then load the matching User
# rows so we have full info (name, vibe text, interests) for the response.
# ---------------------------------------------------------------------------
def find_matches(state: AgentState) -> AgentState:
    """Return up to 3 high-quality matches.

    We over-fetch (top_k=10) and filter, so duplicates and self-matches
    don't shrink the final list below 3.
    """
    raw = find_similar(
        query_text=state["embedding_text"],
        top_k=10,
        exclude_ids=[state["user_id"]],
    )

    # Compare names case-insensitively. ``casefold`` is the Unicode-correct
    # version of ``.lower()`` — important for non-ASCII names.
    own_name = (state.get("name") or "").strip().casefold()

    # We open a fresh DB session here because LangGraph nodes don't have
    # access to the FastAPI request context. Always close it in a finally.
    db: Session = SessionLocal()
    try:
        matches: list[dict] = []
        for m in raw:
            row = db.query(User).filter(User.id == m["user_id"]).one_or_none()
            if row is None:
                # Vector store has a stale id (user deleted from SQL but not Chroma).
                continue
            if own_name and row.name.strip().casefold() == own_name:
                # Skip "twin submissions" — same person posting twice.
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
# Node 4 — generate_icebreakers (parallelized with asyncio.gather)
# For each match, ask the LLM to produce 2 personalised conversation openers.
# ---------------------------------------------------------------------------
ICEBREAKER_SYSTEM = (
    "You write warm, specific icebreaker questions for a social app. "
    "Return STRICT JSON only — no prose, no markdown fences."
)

# Note the doubled ``{{ }}`` braces — they're literal braces in a .format()
# string. Single braces would be interpreted as format placeholders.
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
    """Generate icebreakers for ONE match. Async so we can fan out via gather()."""
    prompt = ICEBREAKER_TEMPLATE.format(
        name_a=state["name"],
        vibe_a=state["vibe_text"],
        interests_a=", ".join(state.get("interests", [])) or "(none)",
        name_b=match["name"],
        vibe_b=match["vibe_text"],
        interests_b=", ".join(match.get("interests", [])) or "(none)",
    )
    try:
        # ``ainvoke`` is the async version of ``invoke`` — required for gather().
        resp = await llm.ainvoke([SystemMessage(content=ICEBREAKER_SYSTEM), HumanMessage(content=prompt)])
        parsed = _safe_parse_json(resp.content, fallback={"icebreakers": []})
        breakers = parsed.get("icebreakers") or []
        if not isinstance(breakers, list):
            breakers = []
        # Truncate to 2 and stringify defensively. The UI assumes a list of strings.
        breakers = [str(b) for b in breakers][:2]
        # If the model gave us fewer than 2, top up with a generic fallback so
        # the UI always shows two openers — looks broken otherwise.
        while len(breakers) < 2:
            breakers.append(f"What's the latest thing you've been into, {match['name']}?")
    except Exception as e:
        log.warning("icebreaker LLM call failed for %s: %s", match["user_id"], e)
        # Hard-fallback if the API is fully unavailable. Still personalised.
        breakers = [
            f"Hey {match['name']}, what's keeping you busy this week?",
            f"What got you into {(match.get('interests') or ['this'])[0]}?",
        ]
    return match["user_id"], breakers


async def _generate_icebreakers_async(state: AgentState) -> dict[str, list[str]]:
    """Fan out one LLM call per match concurrently."""
    matches = state.get("matches", [])
    if not matches:
        return {}
    llm = _llm(temperature=0.7)  # Higher temp ⇒ more creative openers.
    # ``asyncio.gather`` runs all coroutines concurrently and returns a list of
    # results once all have completed. Total time ≈ slowest single call.
    results = await asyncio.gather(*[_icebreaker_for_match(llm, state, m) for m in matches])
    return {uid: ibs for uid, ibs in results}


def generate_icebreakers(state: AgentState) -> AgentState:
    """Sync entry-point that LangGraph calls. Bridges into the async fan-out.

    LangGraph supports async nodes too, but mixing sync+async inside the
    same graph keeps the surrounding FastAPI handler simple.
    """
    icebreakers = asyncio.run(_generate_icebreakers_async(state))
    return {"icebreakers": icebreakers}


# ---------------------------------------------------------------------------
# Graph assembly — wire the four nodes into the linear pipeline.
# ---------------------------------------------------------------------------
def _build_graph():
    """Compile the LangGraph state machine once at import time.

    The compiled graph is reusable and thread-safe — we keep one instance
    in the module-level ``agent_graph`` below.
    """
    graph = StateGraph(AgentState)
    graph.add_node("analyze_vibe", analyze_vibe)
    graph.add_node("embed_and_store", embed_and_store)
    graph.add_node("find_matches", find_matches)
    graph.add_node("generate_icebreakers", generate_icebreakers)

    # Linear edges: START → ... → END. With LangGraph we could later add
    # conditional edges (e.g. skip matching when there are no other users yet).
    graph.add_edge(START, "analyze_vibe")
    graph.add_edge("analyze_vibe", "embed_and_store")
    graph.add_edge("embed_and_store", "find_matches")
    graph.add_edge("find_matches", "generate_icebreakers")
    graph.add_edge("generate_icebreakers", END)

    return graph.compile()


# Single compiled graph reused across requests.
agent_graph = _build_graph()


def run_agent(user_id: str, name: str, vibe_text: str, interests: list[str]) -> AgentState:
    """Run the FULL pipeline for a brand-new user (analyse → store → match → icebreakers)."""
    initial: AgentState = {
        "user_id": user_id,
        "name": name,
        "vibe_text": vibe_text,
        "interests": interests,
    }
    return agent_graph.invoke(initial)


def run_match_only(user_id: str, name: str, vibe_text: str, interests: list[str], embedding_text: str) -> AgentState:
    """Re-run JUST the matching half of the pipeline.

    Used by ``GET /users/{id}/matches`` — the user already exists in the
    vector store and we already have their vibe analysis cached, so we
    can skip ``analyze_vibe`` and ``embed_and_store`` for a much faster
    "refresh matches" experience.
    """
    state: AgentState = {
        "user_id": user_id,
        "name": name,
        "vibe_text": vibe_text,
        "interests": interests,
        "embedding_text": embedding_text,
    }
    # Call the two remaining nodes manually (no graph needed for two steps).
    state.update(find_matches(state))
    state.update(generate_icebreakers(state))
    return state
