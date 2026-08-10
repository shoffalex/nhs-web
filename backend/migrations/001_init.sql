-- Initial schema. Kept as SQL so the production database can be created or
-- inspected without importing the app:
--
--   sqlite3 /var/lib/nhs-web/calendar.db < backend/migrations/001_init.sql
--
-- app/main.py also calls create_all() on startup, so this file is a reference
-- and a recovery path rather than the only way in. If the two ever disagree,
-- models.py is the source of truth.

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
