# Changelog

Notable changes from build to live demo. Reverse chronological.

## v0.1.0 — Live demo (2026-05-03)

First public deploy. URL: https://viberoom-alpha.vercel.app

### Built
- 4-node LangGraph agent: `analyze_vibe → embed_and_store → find_matches → generate_icebreakers`
- 5 REST endpoints, OpenAPI auto-generated
- React 19 frontend with 3 pages (Landing, Create, Matches), Tailwind v4, custom UI primitives
- Multi-stage Docker builds for both services
- Seed script for 8 fictional baseline users so cold demos still produce matches

### Pre-landing review fixes
- **CRITICAL** docker-compose was bind-mounting a single SQLite file. On fresh clones Docker would create a directory there and SQLite would fail. Switched to a parent-dir mount with `DATABASE_URL` and `CHROMA_PERSIST_DIR` overrides.
- Migrated off deprecated `@app.on_event("startup")` to FastAPI lifespan context manager.
- Added Pydantic `Field(ge=1, le=10)` constraint on `energy_level`, plus a `_safe_vibe_analysis()` wrapper so LLM drift falls back to defaults instead of 500ing the request.
- Removed dead `if False else None` branch in `vector_store.find_similar`.
- Moved a mid-file React import to the top of the file.

### Deploy fixes (problems local dev hid)
- **Fly remote builder hit deadline timeout** during `RUN python -c "SentenceTransformer(...)"` model pre-download. Removed pre-download; pointed `HF_HOME` at the persistent volume so the model downloads once on first request and survives redeploys.
- **Python urllib SSL cert verification failed on macOS** when seeding against the live URL. Added explicit `ssl.create_default_context(cafile=certifi.where())` to seed script.
- **CORS env-var parsing**: pydantic-settings doesn't parse comma-separated strings into `list[str]` by default. Refactored Settings to take a string and expose a `cors_origins_list` property.
- **Fly auto-stop too aggressive for demo**: 5-min idle → machine sleeps → next request times out before machine wakes. Disabled auto-stop and set `min_machines_running = 1` for the demo. Trade-off: ~$3-5/mo vs 60s cold starts during interviews.

### Live infra
- Frontend: Vercel (free tier)
- Backend: Fly.io (`shared-cpu-1x`, 1GB RAM, 1GB persistent volume in `iad`)
- LLM: Groq (Llama 3.3 70B, free tier)
- Embeddings: HuggingFace `all-MiniLM-L6-v2` (CPU, local)
