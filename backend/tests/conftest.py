"""Test fixtures: a throwaway SQLite file per test, and two clients.

The database URL and admin credentials are set before app modules are imported,
because database.py builds its engine at import time.
"""

import os
import tempfile
from pathlib import Path

import pytest

TEST_PASSWORD = "test-password"
TEST_SECRET = "test-secret-key"


@pytest.fixture(scope="session", autouse=True)
def _configure_env():
    tmpdir = tempfile.mkdtemp(prefix="nhs-test-")
    db_path = Path(tmpdir) / "test.db"
    os.environ["NHS_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["NHS_ADMIN_PASSWORD"] = TEST_PASSWORD
    os.environ["NHS_SECRET_KEY"] = TEST_SECRET
    yield


@pytest.fixture
def client(_configure_env):
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app

    # Fresh tables per test, so ordering assertions don't depend on run order.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client(client):
    """Same client, with the Authorization header already set."""
    response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['token']}"
    return client
