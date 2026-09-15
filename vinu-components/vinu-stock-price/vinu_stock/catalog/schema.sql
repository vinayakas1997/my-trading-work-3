CREATE TABLE IF NOT EXISTS symbol_catalog (
    symbol            TEXT PRIMARY KEY,
    provider          TEXT NOT NULL DEFAULT '',
    first_bar_ts      INTEGER,
    last_bar_ts       INTEGER,
    archive_through   TEXT,
    live_file         TEXT,
    backfill_status   TEXT NOT NULL DEFAULT 'pending',
    updated_at        INTEGER NOT NULL DEFAULT 0,
    has_adj_data      INTEGER NOT NULL DEFAULT 0,
    gap_count         INTEGER NOT NULL DEFAULT 0,
    last_validation_at INTEGER
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

CREATE TABLE IF NOT EXISTS provider_fallback_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    role            TEXT NOT NULL,
    winning_provider TEXT NOT NULL,
    skipped_errors  TEXT NOT NULL DEFAULT '[]',
    occurred_at     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provider_fallback_log_symbol ON provider_fallback_log(symbol);

CREATE TABLE IF NOT EXISTS backfill_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at          INTEGER NOT NULL,
    symbols         TEXT NOT NULL DEFAULT '[]',
    years_attempted INTEGER NOT NULL DEFAULT 0,
    years_ok        INTEGER NOT NULL DEFAULT 0,
    years_failed    INTEGER NOT NULL DEFAULT 0,
    total_rows      INTEGER NOT NULL DEFAULT 0,
    symbols_skipped INTEGER NOT NULL DEFAULT 0,
    rows_rolled     INTEGER NOT NULL DEFAULT 0,
    errors          TEXT NOT NULL DEFAULT '[]'
);
