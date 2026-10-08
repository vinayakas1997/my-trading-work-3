"""Layer 3 of the news plan: reports of the same story from different sources are one story with tags.

A story is a row in `story_threads` (the thread matcher already groups items by headline similarity, a shared ticker or
entity, and no opposite-result words such as earnings beat vs miss). Layer 3 adds what that table lacked: which sources told
the story and when each first did (`sources_json`, `n_sources`, `first_source`), and it keeps every report as its own raw row
(`is_lead = 0` for all but the first) instead of dropping the later ones. A later report only adds its source to the story and
moves the end time; nothing is re-analysed.
"""
from __future__ import annotations

import json
from typing import Any


def initial_sources(source: str, seen_at: int) -> str:
    return json.dumps([{"source": source, "first_seen_at": int(seen_at)}])


def add_source(conn: Any, thread_id: str, source: str, seen_at: int) -> bool:
    """Record that `source` reported this story. Returns True when it is a source the story did not have yet."""
    row = conn.execute(
        "SELECT sources_json, first_source FROM story_threads WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    if row is None or not source:
        return False
    try:
        sources = json.loads(row["sources_json"] or "[]")
    except json.JSONDecodeError:
        sources = []
    if any(s.get("source") == source for s in sources):
        return False
    sources.append({"source": source, "first_seen_at": int(seen_at)})
    conn.execute(
        "UPDATE story_threads SET sources_json = ?, n_sources = ?, first_source = COALESCE(first_source, ?) WHERE thread_id = ?",
        (json.dumps(sources), len(sources), source, thread_id),
    )
    return True


def story_tags(conn: Any, thread_ids: list[str]) -> dict[str, dict[str, Any]]:
    """The tags a reader sees on an article: how many sources told the story, which, who was first, how many reports."""
    ids = sorted({t for t in thread_ids if t})
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        f"SELECT thread_id, n_sources, sources_json, first_source, first_seen_at, last_seen_at, article_count "
        f"FROM story_threads WHERE thread_id IN ({marks})", ids,
    ).fetchall():
        try:
            names = [s["source"] for s in json.loads(row["sources_json"] or "[]")]
        except (json.JSONDecodeError, KeyError, TypeError):
            names = []
        out[row["thread_id"]] = {
            "story_n_sources": row["n_sources"],
            "story_sources": names,
            "story_first_source": row["first_source"],
            "story_first_seen_at": row["first_seen_at"],
            "story_last_seen_at": row["last_seen_at"],
            "story_n_reports": row["article_count"],
        }
    return out


def migrate_story_sources(conn: Any) -> None:
    """Add the layer-3 columns to `story_threads` and fill them for stories that already exist."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(story_threads)").fetchall()}
    added = False
    for name, definition in (
        ("sources_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("n_sources", "INTEGER NOT NULL DEFAULT 1"),
        ("first_source", "TEXT"),
    ):
        if name in existing:
            continue
        try:
            conn.execute(f"ALTER TABLE story_threads ADD COLUMN {name} {definition}")
        except Exception as exc:  # noqa: BLE001 -- another connection added it first (first start opens several at once)
            if "duplicate column name" not in str(exc):
                raise
            continue
        if name == "sources_json":
            added = True
    if not added:
        return
    conn.commit()
    ids = [r[0] for r in conn.execute("SELECT thread_id FROM story_threads").fetchall()]
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        marks = ",".join("?" for _ in chunk)
        per_thread: dict[str, list[dict[str, Any]]] = {}
        for r in conn.execute(
            f"SELECT thread_id, source, MIN(first_seen_at) AS f FROM articles WHERE thread_id IN ({marks}) "
            f"AND is_current = 1 GROUP BY thread_id, source ORDER BY thread_id, f", chunk,
        ).fetchall():
            per_thread.setdefault(r["thread_id"], []).append({"source": r["source"], "first_seen_at": r["f"]})
        for tid, sources in per_thread.items():
            conn.execute(
                "UPDATE story_threads SET sources_json = ?, n_sources = ?, first_source = ? WHERE thread_id = ?",
                (json.dumps(sources), len(sources), sources[0]["source"], tid),
            )
        conn.commit()
