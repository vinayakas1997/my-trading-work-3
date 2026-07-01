-- SQLite schema for articles, threads, analytics, and feed health

CREATE TABLE IF NOT EXISTS articles (
    id              TEXT PRIMARY KEY,
    headline        TEXT NOT NULL,
    summary         TEXT NOT NULL,
    source          TEXT NOT NULL,
    link            TEXT NOT NULL,
    sort_ts         INTEGER NOT NULL,
    region          TEXT NOT NULL,
    tier            INTEGER NOT NULL,
    category        TEXT NOT NULL,
    priority        TEXT NOT NULL,
    sentiment       TEXT NOT NULL,
    sentiment_score INTEGER NOT NULL,
    impact          TEXT NOT NULL,
    tickers         TEXT NOT NULL,
    lang            TEXT NOT NULL,
    threat_level    TEXT NOT NULL,
    threat_cat      TEXT NOT NULL,
    threat_conf     REAL NOT NULL,
    source_flag     INTEGER NOT NULL DEFAULT 0,
    entities_json   TEXT NOT NULL DEFAULT '{}',
    cluster_id      TEXT,
    is_lead         INTEGER NOT NULL DEFAULT 1,
    thread_id       TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_sort_ts ON articles(sort_ts DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_sort ON articles(source, sort_ts DESC);
CREATE INDEX IF NOT EXISTS idx_articles_impact ON articles(impact, sort_ts DESC);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_thread_id ON articles(thread_id);
CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link);

CREATE TABLE IF NOT EXISTS article_ticker_mentions (
    id          TEXT PRIMARY KEY,
    article_id  TEXT NOT NULL REFERENCES articles(id),
    ticker      TEXT NOT NULL,
    dominance   REAL NOT NULL,
    is_primary  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(article_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_mentions_ticker ON article_ticker_mentions(ticker);
CREATE INDEX IF NOT EXISTS idx_mentions_ticker_article ON article_ticker_mentions(ticker, article_id);

CREATE TABLE IF NOT EXISTS story_threads (
    thread_id         TEXT PRIMARY KEY,
    first_seen_at     INTEGER NOT NULL,
    last_seen_at      INTEGER NOT NULL,
    article_count     INTEGER NOT NULL DEFAULT 1,
    lead_headline     TEXT NOT NULL,
    dominant_ticker   TEXT,
    entities_json     TEXT NOT NULL DEFAULT '{}',
    category          TEXT NOT NULL DEFAULT 'MARKETS',
    last_article_id   TEXT,
    norm_text         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_story_threads_last_seen ON story_threads(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS thread_daily_snapshots (
    thread_id       TEXT NOT NULL REFERENCES story_threads(thread_id),
    date            TEXT NOT NULL,
    article_count   INTEGER NOT NULL DEFAULT 0,
    bullish_count   INTEGER NOT NULL DEFAULT 0,
    bearish_count   INTEGER NOT NULL DEFAULT 0,
    neutral_count   INTEGER NOT NULL DEFAULT 0,
    flash_count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (thread_id, date)
);

CREATE TABLE IF NOT EXISTS ticker_daily_stats (
    ticker          TEXT NOT NULL,
    date            TEXT NOT NULL,
    article_count   INTEGER NOT NULL DEFAULT 0,
    bullish_count   INTEGER NOT NULL DEFAULT 0,
    bearish_count   INTEGER NOT NULL DEFAULT 0,
    neutral_count   INTEGER NOT NULL DEFAULT 0,
    top_thread_id   TEXT,
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_ticker_daily_ticker ON ticker_daily_stats(ticker, date DESC);

CREATE TABLE IF NOT EXISTS feed_health (
    feed_id           TEXT PRIMARY KEY,
    last_success_at   INTEGER,
    last_failure_at   INTEGER,
    fail_streak       INTEGER NOT NULL DEFAULT 0,
    total_polls       INTEGER NOT NULL DEFAULT 0,
    total_failures    INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms    REAL NOT NULL DEFAULT 0,
    last_error        TEXT
);

CREATE TABLE IF NOT EXISTS news_analysis (
    url             TEXT PRIMARY KEY,
    analysis_json   TEXT NOT NULL,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS article_price_reaction (
    article_id        TEXT PRIMARY KEY,
    price_change_1h REAL,
    price_change_1d   REAL,
    computed_at       INTEGER NOT NULL
);
