"""SQLAlchemy database wiring (engine, Session factory, and FastAPI dependency).

Three things live here:

1. ``engine`` — the connection pool to the database. Created once per process.
2. ``SessionLocal`` — a factory that hands out short-lived ``Session`` objects.
   A Session represents a unit of work / transaction. Treat it like a
   "shopping cart" of changes that get persisted on ``commit()``.
3. ``get_db`` — a FastAPI dependency that yields a Session per request and
   guarantees it's closed afterwards (even if the route raises).

Why this layering exists: we want exactly one engine for the whole app, but
many short-lived sessions (one per HTTP request) so that a slow handler
doesn't hold a transaction open.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


# The engine manages a pool of connections to the configured database.
# ``check_same_thread=False`` is a SQLite-only quirk: SQLite by default
# refuses to share a connection across threads, which breaks FastAPI's
# default thread-pool execution model. The flag is meaningless (and
# ignored) for Postgres, so we only set it for sqlite URLs.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

# Session factory. ``autocommit=False`` + ``autoflush=False`` are the
# modern SQLAlchemy defaults: we'll explicitly call ``db.commit()`` so
# that nothing is persisted by accident.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Parent class for every ORM model.

    SQLAlchemy uses ``Base.metadata`` to discover all tables. We call
    ``Base.metadata.create_all(engine)`` at startup (see ``main.lifespan``)
    to auto-create the schema on first run — fine for a hackathon, but in
    a serious project you'd switch to Alembic migrations instead.
    """
    pass


def get_db():
    """FastAPI dependency: yield one Session per request, close on the way out.

    Used like::

        @app.get(...)
        def route(db: Session = Depends(get_db)):
            db.query(...)

    The ``try/finally`` ensures the session is returned to the pool even
    if the route handler raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
