"""Application configuration loaded from environment variables.

We use ``pydantic-settings`` because it gives us:
  * Typed config (string vs int vs list) with automatic validation.
  * Automatic loading from a local ``.env`` file during development.
  * One canonical ``settings`` object to import anywhere in the app — no
    scattered ``os.getenv(...)`` calls.

How it works for a junior engineer:
  1. Create a ``.env`` file next to ``pyproject.toml`` (see ``.env.example``).
  2. Set ``GROQ_API_KEY=...`` (and any other override).
  3. Import ``settings`` and use ``settings.groq_api_key`` etc.

In production (Fly.io / Vercel / etc.) the same names come from the
platform's secrets manager — pydantic-settings reads either source
transparently.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ``env_file=".env"`` — load any matching keys from a local ``.env``.
    # ``extra="ignore"`` — silently skip env vars we don't declare here so
    # adding new platform-level vars never crashes startup.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── LLM (Groq is OpenAI-compatible and very fast for Llama models) ──
    groq_api_key: str = ""  # Required in prod. Empty default keeps tests runnable.
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Persistence ──
    # SQLite by default — zero-config for local dev. Swap to Postgres in prod
    # by setting DATABASE_URL=postgresql+psycopg://user:pass@host/db
    database_url: str = "sqlite:///./viberoom.db"

    # ChromaDB stores vector embeddings on disk in this directory.
    chroma_persist_dir: str = "./chroma_db"

    # Sentence-transformers model used to turn vibe text into a vector.
    # all-MiniLM-L6-v2 is small (~80MB) and produces 384-dim vectors —
    # a good speed/quality trade-off for hackathon-scale apps.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # CORS lets the browser-side frontend (different origin) call this API.
    # Comma-separated list of allowed origins. In production set this to
    # exactly your deployed frontend URL(s) — never use ``*`` with credentials.
    # Example prod value: "https://viberoom.vercel.app,https://www.viberoom.app"
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the CSV string into a clean list for FastAPI's CORS middleware."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Singleton settings instance — import this everywhere instead of re-instantiating.
settings = Settings()
