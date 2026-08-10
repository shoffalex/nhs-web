"""Covers the two things most likely to break: who can write, and what the
public list is allowed to show."""

MEETING = {
    "title": "Chapter meeting",
    "event_date": "2026-09-08",
    "start_time": "13:10:00",
    "location": "MPR",
}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_public_list_starts_empty(client):
    response = client.get("/api/events")
    assert response.status_code == 200
    assert response.json() == []


def test_writes_require_a_token(client):
    assert client.post("/api/events", json=MEETING).status_code == 401
    assert client.patch("/api/events/1", json={"title": "x"}).status_code == 401
    assert client.delete("/api/events/1").status_code == 401


def test_bad_password_is_rejected(client):
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401


def test_create_then_read_publicly(admin_client):
    created = admin_client.post("/api/events", json=MEETING)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["title"] == "Chapter meeting"
    assert event["is_published"] is True

    # Public read needs no token.
    del admin_client.headers["Authorization"]
    listed = admin_client.get("/api/events").json()
    assert [e["id"] for e in listed] == [event["id"]]


def test_unpublished_events_are_hidden_from_the_public(admin_client):
    draft = admin_client.post("/api/events", json={**MEETING, "is_published": False})
    draft_id = draft.json()["id"]

    # Visible to the admin listing...
    assert draft_id in [e["id"] for e in admin_client.get("/api/events/all").json()]

    del admin_client.headers["Authorization"]
    assert admin_client.get("/api/events").json() == []
    # ...and a direct hit must not confirm the draft exists.
    assert admin_client.get(f"/api/events/{draft_id}").status_code == 404


def test_admin_listing_requires_a_token(client):
    assert client.get("/api/events/all").status_code == 401


def test_events_come_back_in_date_order(admin_client):
    for day in ("2026-11-10", "2026-09-08", "2026-10-13"):
        admin_client.post("/api/events", json={**MEETING, "event_date": day})

    dates = [e["event_date"] for e in admin_client.get("/api/events").json()]
    assert dates == ["2026-09-08", "2026-10-13", "2026-11-10"]


def test_date_range_filter(admin_client):
    for day in ("2026-09-08", "2026-10-13", "2026-11-10"):
        admin_client.post("/api/events", json={**MEETING, "event_date": day})

    response = admin_client.get("/api/events", params={"start": "2026-10-01", "end": "2026-10-31"})
    assert [e["event_date"] for e in response.json()] == ["2026-10-13"]


def test_patch_updates_only_what_was_sent(admin_client):
    event_id = admin_client.post("/api/events", json=MEETING).json()["id"]

    patched = admin_client.patch(f"/api/events/{event_id}", json={"location": "Auditorium"})
    assert patched.status_code == 200
    assert patched.json()["location"] == "Auditorium"
    assert patched.json()["title"] == "Chapter meeting"


def test_end_time_must_follow_start_time(admin_client):
    bad = admin_client.post(
        "/api/events", json={**MEETING, "start_time": "13:10:00", "end_time": "12:00:00"}
    )
    assert bad.status_code == 422

    # And the same check must survive a PATCH that only carries end_time.
    event_id = admin_client.post("/api/events", json=MEETING).json()["id"]
    assert admin_client.patch(f"/api/events/{event_id}", json={"end_time": "12:00:00"}).status_code == 422


def test_delete_removes_the_event(admin_client):
    event_id = admin_client.post("/api/events", json=MEETING).json()["id"]
    assert admin_client.delete(f"/api/events/{event_id}").status_code == 204
    assert admin_client.get("/api/events/{event_id}".format(event_id=event_id)).status_code == 404


def test_missing_event_is_404(admin_client):
    assert admin_client.patch("/api/events/9999", json={"title": "x"}).status_code == 404
    assert admin_client.delete("/api/events/9999").status_code == 404
