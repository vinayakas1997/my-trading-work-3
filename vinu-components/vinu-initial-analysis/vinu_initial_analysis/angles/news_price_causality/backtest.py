"""news_price_causality's own backtest glue code.

Group B — not a forecaster, so `run_walk_forward`'s step/future contract
doesn't apply (see plan.md's Group A/B split). Two separate outputs, per
the decided design (04-enhancement-of-each-angle/19-news_price_causality.md
SS5), each with its own real granularity:

- `run_impact_backtest`: one row per article per ticker mention, the
  per-article event study (already point-in-time-safe internally — each
  article's impact is scored using only the price window immediately
  after it, never future information), tagged with the full standard
  5-tag scheme (session/subsession/day-of-week/week/month/quarter) since
  each row has its own real timestamp, same as any other angle's
  per-forecast row.
- `run_aggregate_tests_backtest`: Granger/correlation/lag/significance-eval,
  one set per calendar quarter (not the full tagging scheme — forced by
  those tests' own real minimum-sample floors, see the design doc's SS7).
  Significance-eval reuses ONE full-history impact-row computation
  (correct, un-clipped event windows and full trailing regime history)
  rather than recomputing per-article impact per quarter, then
  retrains/re-evaluates the classifier fresh within each quarter's own
  chronological slice — matching the design's "does causality/predictive
  power hold quarter to quarter" intent without silently degrading the
  event-study windows at quarter boundaries.

No weights store, no naive baseline (per the design doc SS7: each test's
own statistic — Granger's p-value, correlation's bootstrapped CI, the
classifier's lift-over-base-rate — is already "compared to noise" by
construction).
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from vinu_initial_analysis.angles._helpers import calendar_quarter_key as _quarter_key
from vinu_initial_analysis.angles._tagging import tag_row as calendar_tag_row
from vinu_initial_analysis.angles.news_price_causality.compute import (
    _compute_aggregate_tests,
    _compute_impact_rows,
)
from vinu_initial_analysis.angles.news_price_causality.regime_features import build_point_in_time_features
from vinu_initial_analysis.angles.news_price_causality.significance_model import score_significance


def _slice_by_quarter(items: list[dict], ts_fn: Callable[[dict], int]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for item in items:
        ts = ts_fn(item)
        if not ts:
            continue
        buckets.setdefault(_quarter_key(int(ts)), []).append(item)
    return buckets


def run_impact_backtest(
    symbol: str,
    candles: list[dict],
    articles: list[dict],
    price_client: Any = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> pd.DataFrame:
    rows = _compute_impact_rows(symbol, candles, articles, price_client, from_ts, to_ts)
    for row in rows:
        if row.get("type") == "impact" and row.get("ts"):
            row.update(calendar_tag_row(int(row["ts"])))
    return pd.DataFrame(rows)


def run_aggregate_tests_backtest(
    symbol: str,
    candles: list[dict],
    articles: list[dict],
) -> pd.DataFrame:
    rows: list[dict] = []

    candle_buckets = _slice_by_quarter(candles, lambda c: c.get("bar_ts", 0))
    article_buckets = _slice_by_quarter(articles, lambda a: a.get("sort_ts", a.get("ts", 0)))

    for quarter in sorted(set(candle_buckets) | set(article_buckets)):
        q_candles = candle_buckets.get(quarter, [])
        q_articles = article_buckets.get(quarter, [])
        if not q_candles or not q_articles:
            continue
        test_rows = _compute_aggregate_tests(symbol, q_candles, q_articles)
        for r in test_rows:
            r["quarter_key"] = quarter
        rows.extend(test_rows)

    impact_rows = _compute_impact_rows(symbol, candles, articles)
    impact_only = [r for r in impact_rows if r.get("type") == "impact"]
    articles_by_id = {a.get("id"): a for a in articles}
    impact_buckets = _slice_by_quarter(impact_only, lambda r: r.get("ts", 0))
    for quarter, q_impact_rows in sorted(impact_buckets.items()):
        _, _, sig_eval = score_significance(
            q_impact_rows, articles_by_id,
            regime_features=build_point_in_time_features(candles, q_impact_rows),
        )
        if sig_eval is not None:
            rows.append({
                "symbol": symbol, "type": "significance_model_eval",
                "quarter_key": quarter, **sig_eval,
            })

    return pd.DataFrame(rows)
