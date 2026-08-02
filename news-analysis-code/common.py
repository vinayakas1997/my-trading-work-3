"""Shared helpers for the news-analysis experiment scripts.

Reads directly from the vinu-components host data mounts (no docker exec,
no HTTP dependency) so these scripts run standalone with plain `python x.py`.
Nothing here touches vinu-news / vinu-initial-analysis source.
"""

from __future__ import annotations

import glob
import sqlite3
from pathlib import Path

import pandas as pd

DATA_ROOT = Path(r"C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\data")
NEWS_DB = DATA_ROOT / "news" / "news.db"
ANALYSIS_ROOT = DATA_ROOT / "initial-analysis" / "analysis"

TICKERS = ["AAPL", "TSLA", "JNJ"]


def load_impact_events(symbol: str) -> pd.DataFrame:
    """Load the per-article impact/event-study rows for a symbol.

    Picks the most recently written run (mtime) — matches AngleStorage.read()
    in production (vinu_initial_analysis/storage/parquet.py), which was fixed
    to do the same after we found it silently double-counting stale/duplicate
    concurrent runs (see the drawdown_count bug in api.py's get_drawdown).
    Picking by row count instead of mtime is NOT reliable here: an older
    pre-fix run can happen to have the same or a similar row count as the
    latest one.
    """
    import os

    paths = glob.glob(str(ANALYSIS_ROOT / symbol / "news_price_causality" / "*.parquet"))
    if not paths:
        return pd.DataFrame()
    latest_path = max(paths, key=lambda p: os.path.getmtime(p))
    latest_df = pd.read_parquet(latest_path)
    if latest_df.empty:
        return pd.DataFrame()
    events = latest_df[latest_df["type"] == "impact"].copy()
    return events


def load_article_meta(article_ids: list[str]) -> pd.DataFrame:
    """Join back to news.db for fields not stored in the impact parquet
    (category, priority, region) — the impact rows only carry headline/
    sentiment/thread_id, not the raw article metadata.
    """
    if not article_ids:
        return pd.DataFrame()
    conn = sqlite3.connect(str(NEWS_DB))
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in article_ids)
    rows = conn.execute(
        f"SELECT id, category, priority, region, is_lead, finbert_score, finbert_label "
        f"FROM articles WHERE id IN ({placeholders})",
        article_ids,
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows])


def compute_novelty(df: pd.DataFrame, lookback_seconds: int = 3 * 24 * 3600) -> pd.DataFrame:
    """TF-IDF text-similarity novelty score (see 04_real_novelty_score.py
    for the full rationale). Shared here so 04 and 05 use the identical
    definition instead of two scripts silently drifting apart.
    """
    from collections import deque

    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    df = df.dropna(subset=["headline", "ts"]).sort_values("ts").reset_index(drop=True)
    if len(df) < 5:
        return df.assign(novelty_score=1.0)

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(df["headline"].astype(str))

    novelty_scores = np.ones(len(df))
    window: deque[tuple[float, int]] = deque()

    for i in range(len(df)):
        ts_i = df.loc[i, "ts"]
        while window and ts_i - window[0][0] > lookback_seconds:
            window.popleft()
        if window:
            idxs = [idx for _, idx in window]
            sims = cosine_similarity(matrix[i], matrix[idxs]).flatten()
            novelty_scores[i] = 1.0 - sims.max()
        window.append((ts_i, i))

    return df.assign(novelty_score=novelty_scores)


def load_correlation_rows(symbol: str) -> pd.DataFrame:
    paths = glob.glob(str(ANALYSIS_ROOT / symbol / "news_price_causality" / "*.parquet"))
    frames = []
    for p in paths:
        df = pd.read_parquet(p)
        frames.append(df[df["type"] == "correlation"])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
