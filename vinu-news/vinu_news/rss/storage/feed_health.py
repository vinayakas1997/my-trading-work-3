"""Feed health tracking in shared news database."""

from __future__ import annotations

from datetime import datetime, timezone

from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.analysis.storage.repository import NewsRepository


def update_feed_health(
    repo: NewsRepository,
    feed_results: list[FeedPollResult],
) -> None:
    """Upsert feed health rows after each poll cycle."""
    now = int(datetime.now(timezone.utc).timestamp())

    with repo.conn:
        for result in feed_results:
            row = repo.conn.execute(
                "SELECT * FROM feed_health WHERE feed_id = ?",
                (result.feed_id,),
            ).fetchone()

            total_polls = (row["total_polls"] if row else 0) + 1
            total_failures = row["total_failures"] if row else 0
            fail_streak = row["fail_streak"] if row else 0
            avg_latency = row["avg_latency_ms"] if row else 0.0

            if result.success:
                fail_streak = 0
                avg_latency = (
                    (avg_latency * (total_polls - 1) + result.duration_ms) / total_polls
                )
                repo.conn.execute(
                    """
                    INSERT INTO feed_health (
                        feed_id, last_success_at, last_failure_at, fail_streak,
                        total_polls, total_failures, avg_latency_ms, last_error
                    ) VALUES (?, ?, ?, 0, ?, ?, ?, NULL)
                    ON CONFLICT(feed_id) DO UPDATE SET
                        last_success_at = excluded.last_success_at,
                        fail_streak = 0,
                        total_polls = excluded.total_polls,
                        avg_latency_ms = excluded.avg_latency_ms,
                        last_error = NULL
                    """,
                    (
                        result.feed_id,
                        now,
                        row["last_failure_at"] if row else None,
                        total_polls,
                        total_failures,
                        avg_latency,
                    ),
                )
            else:
                total_failures += 1
                fail_streak += 1
                error = result.error or "empty_feed"
                repo.conn.execute(
                    """
                    INSERT INTO feed_health (
                        feed_id, last_success_at, last_failure_at, fail_streak,
                        total_polls, total_failures, avg_latency_ms, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(feed_id) DO UPDATE SET
                        last_failure_at = excluded.last_failure_at,
                        fail_streak = excluded.fail_streak,
                        total_polls = excluded.total_polls,
                        total_failures = excluded.total_failures,
                        last_error = excluded.last_error
                    """,
                    (
                        result.feed_id,
                        row["last_success_at"] if row else None,
                        now,
                        fail_streak,
                        total_polls,
                        total_failures,
                        avg_latency,
                        error,
                    ),
                )

    repo.conn.commit()
