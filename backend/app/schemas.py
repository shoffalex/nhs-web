"""Request and response shapes. These are the API contract the front end codes against."""

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    event_date: date
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_published: bool = True

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    """Every field optional — PATCH semantics, only send what changed.

    Note the end-after-start check can't live here: a PATCH carrying only
    end_time has no start_time to compare against. The route re-validates the
    merged result instead.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    event_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_published: bool | None = None


class EventOut(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    expires_in: int  # seconds
