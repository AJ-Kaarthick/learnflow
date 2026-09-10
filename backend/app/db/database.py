from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def is_sqlite_url(database_url: str) -> bool:
    """
    True for any SQLite URL (sqlite:///... or sqlite+pysqlite:///...).
    Centralized here (rather than repeating `.startswith("sqlite")` at
    every call site that needs a dialect-specific behavior -- see
    build_engine below and alembic/env.py's batch-mode setup) so
    there's exactly one place that decides what counts as "SQLite" if
    that ever needs to get more precise.
    """
    return database_url.startswith("sqlite")


def build_engine(database_url: str) -> Engine:
    """
    Creates a SQLAlchemy Engine for `database_url`, with SQLite-only
    connection quirks applied conditionally rather than unconditionally.

    V3 Milestone 2 Phase 1: previously this project only ever ran
    against SQLite, so `connect_args={"check_same_thread": False}` was
    hardcoded directly into a single module-level `create_engine()`
    call. That flag is meaningless (and, worse, an invalid keyword
    argument for the DBAPI) to any other database -- passing it to
    psycopg2 for a PostgreSQL URL would fail outright. Shared by both
    the application's own `engine` below and alembic/env.py, so a
    migration run and the app itself always construct their engine the
    same way for whatever `database_url` they're each given.

    `pool_pre_ping=True` is applied for every dialect: it issues a
    cheap liveness check before handing out a pooled connection and
    transparently reconnects if that fails. This is a no-op in
    practice for SQLite's typically-short-lived local file connections,
    but it's what protects a long-running PostgreSQL deployment from
    "server closed the connection unexpectedly" errors after a period
    of idleness -- exactly the kind of production concern that didn't
    exist yet when this project only targeted a local SQLite file.
    """
    connect_args = {"check_same_thread": False} if is_sqlite_url(database_url) else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


engine = build_engine(settings.database_url)

# A factory that produces new database sessions. autocommit=False and
# autoflush=False give us explicit control over when changes are sent
# to the database, rather than SQLAlchemy guessing.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The base class every model (see models.py) inherits from. SQLAlchemy
# uses it to track which classes map to which database tables. Also
# the source of truth alembic/env.py imports as `target_metadata` for
# autogenerate and for building migrations against.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that hands a route a database session and
    guarantees it's closed afterward — even if the route raises an
    exception. Routes use it like:

        def some_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
