"""Database engine and session setup.

DATABASE_URL is a standard Postgres URL (as given by Neon) or a SQLite URL for local use.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def normalize_url(url):
    """Make provider URLs (postgres:// or postgresql://) use the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def database_url():
    return normalize_url(os.environ.get("DATABASE_URL", "sqlite:///padelstats.db"))


def make_engine(url=None):
    return create_engine(url or database_url(), pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
