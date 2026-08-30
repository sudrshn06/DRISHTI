"""
DRISHTI Backend — Database Session

SQLAlchemy 2.x engine and session factory.
Only connection configuration — no models defined in Phase 0.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # verify connection before use
    echo=settings.app_debug,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base — all models will inherit from this."""
    pass


def get_db():
    """FastAPI dependency: yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Verify database connectivity.
    Returns True if connection is successful, raises on failure.
    Used by health endpoint.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
