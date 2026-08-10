"""Calendar events. Reads are public; writes require the admin token."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Event
from ..schemas import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])


def _get_or_404(event_id: int, db: Session) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    return event


@router.get("", response_model=list[EventOut])
def list_events(
    db: Session = Depends(get_db),
    start: date | None = Query(None, description="Only events on or after this date"),
    end: date | None = Query(None, description="Only events on or before this date"),
    limit: int = Query(500, ge=1, le=2000),
):
    stmt = select(Event).order_by(Event.event_date, Event.start_time)

    if start is not None:
        stmt = stmt.where(Event.event_date >= start)
    if end is not None:
        stmt = stmt.where(Event.event_date <= end)

    # Unpublished events stay hidden here no matter what the query string says.
    # The admin page uses GET /api/events/all instead, which is token-gated —
    # keeping the two paths separate means a typo in this filter can't leak drafts.
    stmt = stmt.where(Event.is_published.is_(True))

    return db.scalars(stmt.limit(limit)).all()


@router.get("/all", response_model=list[EventOut], dependencies=[Depends(require_admin)])
def list_all_events(db: Session = Depends(get_db), limit: int = Query(2000, ge=1, le=5000)):
    """Every event including unpublished drafts. Powers the admin page."""
    stmt = select(Event).order_by(Event.event_date, Event.start_time).limit(limit)
    return db.scalars(stmt).all()


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = _get_or_404(event_id, db)
    if not event.is_published:
        # Same 404 as a missing row: don't confirm that a draft exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found.")
    return event


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_event(body: EventCreate, db: Session = Depends(get_db)):
    event = Event(**body.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}", response_model=EventOut, dependencies=[Depends(require_admin)])
def update_event(event_id: int, body: EventUpdate, db: Session = Depends(get_db)):
    event = _get_or_404(event_id, db)

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(event, field, value)

    # Re-check the time ordering against the merged row: EventUpdate can't do it
    # alone, since a PATCH may carry only one of the two times.
    if event.start_time and event.end_time and event.end_time <= event.start_time:
        # Literal 422 rather than status.HTTP_422_*: Starlette renamed the
        # constant, and the old name now warns while the new one doesn't exist
        # in older releases.
        raise HTTPException(422, "end_time must be later than start_time")

    db.commit()
    db.refresh(event)
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(event_id, db))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
