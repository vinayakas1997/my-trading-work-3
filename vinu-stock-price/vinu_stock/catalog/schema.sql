CREATE TABLE IF NOT EXISTS symbol_catalog (
    symbol            TEXT PRIMARY KEY,
    provider          TEXT NOT NULL DEFAULT '',
    interval          TEXT NOT NULL DEFAULT '1m',
    first_bar_ts      INTEGER,
    last_bar_ts       INTEGER,
    archive_through   TEXT,
    live_file         TEXT,
    backfill_status   TEXT NOT NULL DEFAULT 'pending',
    updated_at        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS backfill_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        TEXT NOT NULL,
    year          INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'queued',
    provider      TEXT,
    rows_written  INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    updated_at    INTEGER NOT NULL DEFAULT 0,
    UNIQUE(symbol, year)
);

CREATE INDEX IF NOT EXISTS idx_backfill_jobs_status ON backfill_jobs(status);

CREATE TABLE IF NOT EXISTS ingest_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT,
    run_at      INTEGER NOT NULL,
    bars_added  INTEGER NOT NULL DEFAULT 0,
    from_ts     INTEGER,
    to_ts       INTEGER,
    ok          INTEGER NOT NULL DEFAULT 1,
    error       TEXT
);
