"""Test fixtures: a throwaway SQLite file per session, and two clients.

The database path and admin credentials are set before app modules are
imported, because config's get_settings() caches on first use.
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
    os.environ["NHS_DB_PATH"] = str(Path(tmpdir) / "test.db")
    os.environ["NHS_ADMIN_PASSWORD"] = TEST_PASSWORD
    os.environ["NHS_SECRET_KEY"] = TEST_SECRET
    yield


@pytest.fixture
def client(_configure_env):
    from fastapi.testclient import TestClient

    from app.database import connect, init_db
    from app.main import app
    from app.routers.auth import _failures

    # Fresh table and a clean throttle per test, so ordering assertions and
    # login counts don't depend on run order.
    conn = connect()
    conn.execute("DROP TABLE IF EXISTS events")
    conn.commit()
    conn.close()
    init_db()
    _failures.clear()

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client(client):
    """Same client, with the Authorization header already set."""
    response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['token']}"
    return client
