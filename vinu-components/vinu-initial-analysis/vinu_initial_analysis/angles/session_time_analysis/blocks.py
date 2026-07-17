from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from vinu_initial_analysis.angles.session_time_analysis.calendar import get_market_sessions
from vinu_initial_analysis.angles.news_price_causality.correlation import compute_correlation, resample_news_to_hourly, resample_returns_to_hourly
from vinu_initial_analysis.angles.session_time_analysis.market_hours import classify_session, iter_session_names


def compute_time_gaps(events: list[dict]) -> list[dict[str, Any]]:
    sorted_events = sorted(events, key=lambda e: e.get("ts", 0))
    gaps = []
    for i in range(1, len(sorted_events)):
        prev = sorted_events[i - 1]
        curr = sorted_events[i]
        prev_ts = prev.get("ts", 0)
        curr_ts = curr.get("ts", 0)
        gap_sec = curr_ts - prev_ts
        gaps.append({
            "gap_hours": round(gap_sec / 3600, 4),
            "gap_seconds": gap_sec,
            "before_ts": prev_ts,
            "after_ts": curr_ts,
            "before_headline": prev.get("headline", ""),
            "after_headline": curr.get("headline", ""),
            "before_session": prev.get("session", classify_session(prev_ts).name),
            "after_session": curr.get("session", classify_session(curr_ts).name),
        })
    return gaps


def compute_correlation_by_session(
    articles: list[dict],
    candles: list[dict],
) -> dict[str, Any]:
    from vinu_initial_analysis.angles.session_time_analysis.market_hours import classify_session

    by_session_articles: dict[str, list[dict]] = defaultdict(list)
    by_session_candles: dict[str, list[dict]] = defaultdict(list)

    for a in articles:
        session = classify_session(a.get("sort_ts", a.get("ts", 0))).name
        by_session_articles[session].append(a)

    for c in candles:
        session = classify_session(c.get("bar_ts", 0)).name
        by_session_candles[session].append(c)

    results = {}
    for sname in iter_session_names():
        sess_articles = by_session_articles.get(sname, [])
        sess_candles = by_session_candles.get(sname, [])
        if len(sess_articles) < 3 or len(sess_candles) < 5:
            continue
        news_hourly = resample_news_to_hourly(sess_articles)
        returns_hourly = resample_returns_to_hourly(sess_candles)
        if len(news_hourly) < 3 or len(returns_hourly) < 3:
            continue
        corr = compute_correlation(news_hourly, returns_hourly, n_bootstrap=200)
        results[sname] = {
            "pearson": corr["news_return_corr"],
            "p_value": corr["corr_p_value"],
            "sample_hours": corr["sample_size"],
        }

    return results


def analyze_session_transition(
    articles: list[dict],
    candles: list[dict],
    pre_session: str,
    post_session: str,
    date: str | None = None,
) -> dict[str, Any]:
    from vinu_initial_analysis.angles.session_time_analysis.calendar import get_market_sessions

    boundary_hour = None
    ref_dt = datetime.now(timezone.utc)
    if date:
        try:
            ref_dt = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    if isinstance(ref_dt, int):
        ref_dt = datetime.fromtimestamp(ref_dt, tz=timezone.utc)

    sessions = get_market_sessions(ref_dt)
    boundary_found = False
    for i, s in enumerate(sessions):
        if s["name"] == pre_session and i + 1 < len(sessions) and sessions[i + 1]["name"] == post_session:
            boundary_hour = s["utc_end"]
            boundary_found = True
            break

    if not boundary_found or boundary_hour is None:
        return {"avg_gap_pct": None, "news_correlation": None, "samples": 0}

    boundary_margin = 3600
    boundary_ts_low = (ref_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                       + boundary_hour * 3600 - boundary_margin)
    boundary_ts_high = boundary_ts_low + 2 * boundary_margin

    near_boundary = [
        a for a in articles
        if boundary_ts_low <= a.get("sort_ts", a.get("ts", 0)) <= boundary_ts_high
    ]

    pre_candles = [c for c in candles if c.get("bar_ts", 0) < boundary_ts_low + boundary_margin]
    post_candles = [c for c in candles if c.get("bar_ts", 0) >= boundary_ts_low + boundary_margin
                    and c.get("bar_ts", 0) <= boundary_ts_high]

    pre_close = None
    for c in sorted(pre_candles, key=lambda x: x.get("bar_ts", 0), reverse=True):
        pre_close = c.get("close")
        break

    post_open = None
    for c in sorted(post_candles, key=lambda x: x.get("bar_ts", 0)):
        post_open = c.get("open")
        break

    gap_pct = None
    if pre_close and post_open and pre_close != 0:
        gap_pct = round((post_open - pre_close) / pre_close * 100, 4)

    news_corr = None
    if len(near_boundary) > 1:
        scores = [abs(a.get("price_change_30m", 0) or 0) for a in near_boundary]
        timeliness = [abs(a.get("ts", 0) - (boundary_ts_low + boundary_margin)) for a in near_boundary]
        if len(scores) > 1 and sum(scores) > 0:
            avg_score = sum(scores) / len(scores)
            max_score = max(scores)
            news_corr = round(avg_score / max_score, 4) if max_score > 0 else 0.0

    return {
        "avg_gap_pct": gap_pct,
        "news_correlation": news_corr,
        "samples": len(near_boundary),
    }


def compute_premarket_gap(
    articles: list[dict],
    date: str | None = None,
) -> dict[str, Any]:
    from vinu_initial_analysis.angles.session_time_analysis.calendar import get_market_sessions, is_dst

    ref_ts = int(datetime.now(timezone.utc).timestamp())
    if date:
        try:
            ref_dt = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            ref_ts = int(ref_dt.timestamp())
        except (ValueError, TypeError):
            pass
    ref_dt = datetime.fromtimestamp(ref_ts, tz=timezone.utc)

    sessions = get_market_sessions(ref_dt)
    reg_open = None
    pre_end = None
    for s in sessions:
        if s["name"] == "ny_regular":
            reg_open = s["utc_start"]
        if s["name"] == "ny_premarket":
            pre_end = s["utc_end"]

    if reg_open is None:
        return {"gap_hours": None, "error": "no ny_regular session found"}

    day_start = (ref_ts // 86400) * 86400
    market_open_ts = day_start + reg_open * 3600

    premarket_articles = [
        a for a in articles
        if a.get("session", "") == "ny_premarket"
        or a.get("sort_ts", a.get("ts", 0)) < market_open_ts
    ]

    if not premarket_articles:
        return {"gap_hours": None, "last_article_ts": None, "last_headline": None, "market_open_ts": market_open_ts}

    last = max(premarket_articles, key=lambda a: a.get("sort_ts", a.get("ts", 0)))
    last_ts = last.get("sort_ts", last.get("ts", 0))
    gap_sec = max(0, market_open_ts - last_ts)

    return {
        "gap_hours": round(gap_sec / 3600, 4),
        "last_article_ts": last_ts,
        "last_headline": last.get("headline", ""),
        "market_open_ts": market_open_ts,
        "session": last.get("session", classify_session(last_ts).name),
    }
