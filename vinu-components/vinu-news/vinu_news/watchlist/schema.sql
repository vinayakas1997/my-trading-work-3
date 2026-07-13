CREATE TABLE IF NOT EXISTS watchlist_tickers (
    ticker        TEXT PRIMARY KEY,
    added_at      INTEGER NOT NULL,
    pending_fetch INTEGER NOT NULL DEFAULT 0
);
