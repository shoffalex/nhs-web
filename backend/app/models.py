"""Database tables.

One table for now. `event_date` is a plain date and `start_time`/`end_time` are
plain times rather than one UTC timestamp: a chapter meeting is "1:10 pm at
school", a wall-clock fact, and storing it as an instant would make it drift
across daylight-saving boundaries.
"""

from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, Index, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lets you stage next year's schedule before members can see it.
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_events_date", "event_date"),)

    def __repr__(self) -> str:
        return f"<Event {self.id} {self.event_date} {self.title!r}>"
