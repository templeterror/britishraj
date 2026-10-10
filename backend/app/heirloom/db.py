from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

SCHEMA = "heirloom"

# Unbound: each app binds it to its own engine (`request.app.state.engine`).
SessionFactory = sessionmaker(expire_on_commit=False)


def make_engine(url: str) -> Engine:
    """SQLite (demo/tests) runs without schemas; Postgres keeps the `heirloom` schema."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if parsed.database in (None, "", ":memory:"):
        kwargs["poolclass"] = StaticPool  # one shared connection so every session sees the same memory DB
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine.execution_options(schema_translate_map={SCHEMA: None})


def init_db(engine: Engine) -> None:
    """Create the heirloom tables (and the Postgres schema) if they do not exist."""
    from app.heirloom.models import Base

    if engine.dialect.name == "sqlite":
        database = engine.url.database
        if database and database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
    else:
        with engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    Base.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: commit when the request succeeds, roll back when it raises."""
    session = SessionFactory(bind=request.app.state.engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
