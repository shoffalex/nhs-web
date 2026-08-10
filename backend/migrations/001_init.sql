-- The schema. app/database.py executes this at startup (everything is
-- IF NOT EXISTS, so that is safe on every boot), and it works standalone too:
--
--   sqlite3 /var/lib/nhs-web/calendar.db < backend/migrations/001_init.sql
--
-- This file is the single source of truth — there is no ORM model to drift
-- from it.

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         VARCHAR(200) NOT NULL,
    event_date    DATE         NOT NULL,
    start_time    TIME,
    end_time      TIME,
    location      VARCHAR(200),
    description   TEXT,
    is_published  BOOLEAN      NOT NULL DEFAULT 1,
    created_at    DATETIME,
    updated_at    DATETIME
);

CREATE INDEX IF NOT EXISTS ix_events_date ON events (event_date);
