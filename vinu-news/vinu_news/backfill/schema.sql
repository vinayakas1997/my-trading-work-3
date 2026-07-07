CREATE TABLE IF NOT EXISTS backfill_status (
    ticker              TEXT PRIMARY KEY,
    enabled             INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'pending',
    backfilled_up_to_ts INTEGER,
    oldest_ts           INTEGER,
    article_count       INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    updated_at          INTEGER NOT NULL DEFAULT 0
);
