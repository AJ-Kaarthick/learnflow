from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# SQLite, by default, only lets the thread that opened a connection use
# it. FastAPI can serve a single request across different threads, so
# we disable that check. This flag is SQLite-specific — it won't be
# needed if we move to Postgres later.
engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)

# A factory that produces new database sessions. autocommit=False and
# autoflush=False give us explicit control over when changes are sent
# to the database, rather than SQLAlchemy guessing.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The base class every model (see models.py) inherits from. SQLAlchemy
# uses it to track which classes map to which database tables.
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
