"""Calendar events. Reads are public; writes require the admin token.

Rows travel as sqlite3.Row → dict → EventOut. Dates and times are stored as
ISO-8601 text ("2026-09-08", "13:10:00"), which sorts chronologically as plain
strings and round-trips through Pydantic.
"""

import sqlite3
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..auth import require_admin
from ..database import get_db
from ..schemas import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])

_FIELDS = (
    "title",
    "event_date",
    "start_time",
    "end_time",
    "location",
    "description",
    "is_published",
)


def _to_sql(value):
    """Pydantic value → something sqlite3 can bind."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_or_404(event_id: int, db: sqlite3.Connection) -> sqlite3.Row:
    row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    return row


@router.get("", response_model=list[EventOut])
def list_events(
    db: sqlite3.Connection = Depends(get_db),
    start: date | None = Query(None, description="Only events on or after this date"),
    end: date | None = Query(None, description="Only events on or before this date"),
    limit: int = Query(500, ge=1, le=2000),
):
    # Unpublished events stay hidden here no matter what the query string says.
    # The admin page uses GET /api/events/all instead, which is token-gated —
    # keeping the two paths separate means a typo in this filter can't leak drafts.
    sql = "SELECT * FROM events WHERE is_published = 1"
    params: list = []

    if start is not None:
        sql += " AND event_date >= ?"
        params.append(start.isoformat())
    if end is not None:
        sql += " AND event_date <= ?"
        params.append(end.isoformat())

    sql += " ORDER BY event_date, start_time LIMIT ?"
    params.append(limit)

    return [dict(row) for row in db.execute(sql, params)]


@router.get("/all", response_model=list[EventOut], dependencies=[Depends(require_admin)])
def list_all_events(
    db: sqlite3.Connection = Depends(get_db), limit: int = Query(2000, ge=1, le=5000)
):
    """Every event including unpublished drafts. Powers the admin page."""
    rows = db.execute(
        "SELECT * FROM events ORDER BY event_date, start_time LIMIT ?", (limit,)
    )
    return [dict(row) for row in rows]


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = _get_or_404(event_id, db)
    if not row["is_published"]:
        # Same 404 as a missing row: don't confirm that a draft exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    return dict(row)


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_event(body: EventCreate, db: sqlite3.Connection = Depends(get_db)):
    data = body.model_dump()
    now = _utcnow()
    placeholders = ", ".join("?" for _ in range(len(_FIELDS) + 2))
    cur = db.execute(
        f"INSERT INTO events ({', '.join(_FIELDS)}, created_at, updated_at)"
        f" VALUES ({placeholders})",
        [_to_sql(data[f]) for f in _FIELDS] + [now, now],
    )
    db.commit()
    return dict(_get_or_404(cur.lastrowid, db))


@router.patch("/{event_id}", response_model=EventOut, dependencies=[Depends(require_admin)])
def update_event(event_id: int, body: EventUpdate, db: sqlite3.Connection = Depends(get_db)):
    row = _get_or_404(event_id, db)

    changes = {k: _to_sql(v) for k, v in body.model_dump(exclude_unset=True).items()}
    if changes:
        # Re-check the time ordering against the merged row: EventUpdate can't do it
        # alone, since a PATCH may carry only one of the two times. Comparing the
        # ISO strings works because "HH:MM:SS" is fixed-width.
        merged = {**dict(row), **changes}
        if (
            merged["start_time"]
            and merged["end_time"]
            and merged["end_time"] <= merged["start_time"]
        ):
            # Literal 422 rather than status.HTTP_422_*: Starlette renamed the
            # constant, and the old name now warns while the new one doesn't exist
            # in older releases.
            raise HTTPException(422, "end_time must be later than start_time")

        assignments = ", ".join(f"{field} = ?" for field in changes)
        db.execute(
            f"UPDATE events SET {assignments}, updated_at = ? WHERE id = ?",
            [*changes.values(), _utcnow(), event_id],
        )
        db.commit()

    return dict(_get_or_404(event_id, db))


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_event(event_id: int, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("DELETE FROM events WHERE id = ?", (event_id,)).rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
