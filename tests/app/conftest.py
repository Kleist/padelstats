"""Fixtures for the web app: a migrated database and a test client."""

import os

os.environ.setdefault("COOKIE_SECURE", "0")
os.environ["ADMIN_PASSWORD"] = "hemmelig"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import get_session, make_engine, normalize_url  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def engine(tmp_path):
    """Fresh database migrated with Alembic. Uses TEST_DATABASE_URL (Postgres) if set, else SQLite."""
    url = os.environ.get("TEST_DATABASE_URL")
    url = normalize_url(url) if url else f"sqlite:///{tmp_path / 'test.db'}"
    engine = make_engine(url)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with Session() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"password": "hemmelig"})
    return client
