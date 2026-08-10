"""The in-process login throttle — the piece that replaced nginx's limit_req."""

from conftest import TEST_PASSWORD


def test_login_throttles_after_repeated_failures(client):
    for _ in range(10):
        response = client.post("/api/auth/login", json={"password": "wrong"})
        assert response.status_code == 401

    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 429
    # Once tripped, even the right password waits out the window.
    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 429


def test_failures_below_the_limit_do_not_throttle(client):
    for _ in range(9):
        client.post("/api/auth/login", json={"password": "wrong"})

    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 200


def test_successful_logins_do_not_count_toward_the_limit(client):
    for _ in range(11):
        assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 200
