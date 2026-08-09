"""The angle registry — maps angle name to its real backtest entry point,
so run_batch() can build real (symbol, angle_name, work_fn) jobs without
each caller re-deriving which angle needs which call shape.

Deliberately separate from orchestration.py: that module is generic and
angle-agnostic (same separation the walk-forward harness keeps from any
one angle's own backtest.py). This is the angle-specific glue, the same
role backtest.py plays over walk_forward.py.

Scope: 29 angles. 24 whose real backtest entry point takes just
(symbol, [timeframe,] bars[, data_root]) with any other inputs (news,
peer/price clients) genuinely optional -- checked directly against every
angle's own backtest.py, not assumed. An earlier pass wrongly excluded
`drawdown_deep_dive` and `shock_personality` as "needs extra data" /
"no usable entry point" without actually reading their signatures: both
take an optional `news` param defaulting to None and produce their full
real value without it (confirmed against shock_personality's own real
2026 05-shock_personality data, where the `_no_news` variant already
carries the full real sample).

Plus 5 more, wired in a follow-up pass once each one's real extra-data
need was actually satisfied rather than left as an exclusion reason (see
New-talk-/07-orchestration-suite-test/03-still-open-not-wired.md for the
original reasoning this pass closed out):
- `news_price_causality_impact` / `news_price_causality_aggregate` --
  `articles` (a real, non-optional positional arg) is now fetched per
  symbol via `NewsRepository.get_news_for_ticker()` (vinu-news's own
  real repository), injected through `build_batch_jobs(news_repository=...)`.
- `peer_relative_strength` / `peer_relative_strength_forward_validation`
  -- `price_client` is now real: either the production `PriceClient`
  (HTTP, `clients/price_client.py`) or `LocalPriceClient`
  (`clients/local_price_client.py`, no server needed, reads real cached
  bars via `vinu_stock.query.engine.fetch_candles`), injected through
  `build_batch_jobs(price_client=...)`.
- `trend_session_structure` -- has no bars-only entry point of its own
  (it aggregates `trend_lifecycle`'s own signal-outcome output by
  session). Rather than adding real job-dependency scheduling to
  `run_batch` (a generic tracker with no dependency notion), its
  registry entry recomputes `trend_lifecycle`'s own real backtest inline
  -- cheap, deterministic, and the batch already runs `trend_lifecycle`
  as its own separate job anyway.

Plus `pnl_attribution` -- consumes trade/position data, not `bars`, so it
doesn't fit any bars-based shape at all. Wired via a new `"positions"`
shape: the caller supplies already-fetched real closed positions per
symbol through `build_batch_jobs(positions_by_symbol=...)` -- e.g. real
output from `vinu_live.book.positions.list_closed_positions(book_backend,
symbol=...)`. Registry module itself has zero import on `vinu_live` (same
convention as `news_repository`/`price_client`: duck-typed data the
caller already fetched, not a concrete class this module owns). No real
Phase 6 (live trading) positions exist in this project yet, so a real
batch run against a real, currently-empty `BookBackend` honestly returns
`status: "no_data"` per symbol -- that's the angle's own correct,
documented behavior on an empty book, not a placeholder this pass faked.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable
from uuid import uuid4

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.arima.backtest import MIN_OBSERVATIONS as _ARIMA_MIN_OBS
from vinu_initial_analysis.angles.arima.backtest import arima_step, run_arima_backtest
from vinu_initial_analysis.angles.backtesting_44_metrics.backtest import run_core_metrics_backtest
from vinu_initial_analysis.angles.chronos.backtest import HORIZON as _CHRONOS_HORIZON
from vinu_initial_analysis.angles.chronos.backtest import MIN_OBSERVATIONS as _CHRONOS_MIN_OBS
from vinu_initial_analysis.angles.chronos.backtest import chronos_step, run_chronos_backtest
from vinu_initial_analysis.angles.dlinear.backtest import run_dlinear_backtest
from vinu_initial_analysis.angles.drawdown_deep_dive.backtest import run_drawdown_detection
from vinu_initial_analysis.angles.exponential_smoothing.backtest import MIN_OBSERVATIONS as _ES_MIN_OBS
from vinu_initial_analysis.angles.exponential_smoothing.backtest import es_step, run_es_backtest
from vinu_initial_analysis.angles.garch.backtest import MIN_OBSERVATIONS as _GARCH_MIN_OBS
from vinu_initial_analysis.angles.garch.backtest import _garch_step, run_garch_backtest
from vinu_initial_analysis.angles.itransformer.backtest import run_itransformer_backtest
from vinu_initial_analysis.angles.kalman_filters.backtest import MIN_OBSERVATIONS as _KALMAN_MIN_OBS
from vinu_initial_analysis.angles.kalman_filters.backtest import kalman_step, run_kalman_backtest
from vinu_initial_analysis.angles.kronos.backtest import HORIZON as _KRONOS_HORIZON
from vinu_initial_analysis.angles.kronos.backtest import WALK_FORWARD_MIN_OBSERVATIONS as _KRONOS_MIN_OBS
from vinu_initial_analysis.angles.kronos.backtest import kronos_step, run_kronos_backtest
from vinu_initial_analysis.angles.lag_llama.backtest import run_lag_llama_backtest
from vinu_initial_analysis.angles.lpatchtst.backtest import run_lpatchtst_backtest
from vinu_initial_analysis.angles.lstm.backtest import run_lstm_backtest
from vinu_initial_analysis.angles.moirai.backtest import run_moirai_backtest
from vinu_initial_analysis.angles.moment.backtest import run_moment_backtest
from vinu_initial_analysis.angles.news_price_causality.backtest import (
    run_aggregate_tests_backtest,
    run_impact_backtest,
)
from vinu_initial_analysis.angles.patchtst.backtest import run_patchtst_backtest
from vinu_initial_analysis.angles.peer_relative_strength.backtest import (
    run_forward_return_validation,
    run_relative_strength_backtest,
)
from vinu_initial_analysis.angles.pnl_attribution.compute import aggregate_pnl_attribution
from vinu_initial_analysis.angles.regime_analysis.backtest import run_per_bar_regime_backtest
from vinu_initial_analysis.angles.shock_clustering.backtest import run_shock_date_backtest
from vinu_initial_analysis.angles.shock_personality.backtest import run_shock_backtest
from vinu_initial_analysis.angles.tft.backtest import run_tft_backtest
from vinu_initial_analysis.angles.timer_timerxl.backtest import HORIZON as _TIMER_HORIZON
from vinu_initial_analysis.angles.timer_timerxl.backtest import MIN_OBSERVATIONS as _TIMER_MIN_OBS
from vinu_initial_analysis.angles.timer_timerxl.backtest import (
    run_timer_timerxl_backtest,
    timer_timerxl_step,
)
from vinu_initial_analysis.angles.timesfm.backtest import run_timesfm_backtest
from vinu_initial_analysis.angles.tips_regime_aware_transformer.backtest import run_tips_backtest
from vinu_initial_analysis.angles.trend_lifecycle.backtest import run_signal_outcome_backtest
from vinu_initial_analysis.angles.trend_session_structure.backtest import (
    aggregate_signal_outcomes_by_session,
)
from vinu_initial_analysis.storage.factsheet import write_factsheet, write_summary
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.orchestration import AngleRunStatus, run_batch
from vinu_initial_analysis.storage.parquet import AngleStorage
from vinu_tools.compute.backtest.walk_forward import (
    BatchResult,
    WalkForwardJob,
    run_walk_forward_parallel_batch,
)

def _run_trend_session_structure_chained(symbol: str, bars: pd.DataFrame, time_format: str) -> pd.DataFrame:
    """trend_session_structure has no bars-only entry point of its own --
    it aggregates trend_lifecycle's own signal-outcome output by session.
    Rather than adding real job-dependency scheduling to run_batch (a
    generic tracker with no dependency notion -- see
    07-orchestration-suite-test/03-still-open-not-wired.md), this simply
    recomputes trend_lifecycle's own real backtest inline: cheap and
    deterministic, and the batch already runs trend_lifecycle as its own
    separate job anyway, so this trades a small amount of duplicate real
    compute for staying inside the existing independent-job model."""
    signal_outcomes = run_signal_outcome_backtest(symbol, bars, time_format=time_format)
    return aggregate_signal_outcomes_by_session(signal_outcomes)


# call shape -> how build_work_fn assembles the real positional call.
# "std":             run_fn(symbol, timeframe, bars)
# "std_data_root":   run_fn(symbol, timeframe, bars, data_root)  -- trained-
#                     from-scratch angles needing WeightsStore(data_root)
# "bars_time_format": run_fn(symbol, bars, time_format)
# "bars_only":        run_fn(symbol, bars)
# "bars_articles":    run_fn(symbol, candles, articles)  -- candles is
#                     bars.to_dict("records"); articles comes from
#                     build_batch_jobs(news_repository=...)
# "bars_price_client": run_fn(symbol, bars, price_client=...)  -- price_client
#                     comes from build_batch_jobs(price_client=...)
# "positions":        run_fn(symbol, positions)  -- positions (real closed
#                     trade data, not bars) comes from
#                     build_batch_jobs(positions_by_symbol=...)
ANGLE_REGISTRY: dict[str, tuple[Callable[..., pd.DataFrame], str]] = {
    "chronos": (run_chronos_backtest, "std"),
    "exponential_smoothing": (run_es_backtest, "std"),
    "garch": (run_garch_backtest, "std"),
    "kalman_filters": (run_kalman_backtest, "std"),
    "kronos": (run_kronos_backtest, "std"),
    "lag_llama": (run_lag_llama_backtest, "std"),
    "moirai": (run_moirai_backtest, "std"),
    "moment": (run_moment_backtest, "std"),
    "timesfm": (run_timesfm_backtest, "std"),
    "timer_timerxl": (run_timer_timerxl_backtest, "std"),
    "backtesting_44_metrics": (run_core_metrics_backtest, "std"),
    "arima": (run_arima_backtest, "std_data_root"),
    "dlinear": (run_dlinear_backtest, "std_data_root"),
    "drawdown_deep_dive": (run_drawdown_detection, "std"),
    "itransformer": (run_itransformer_backtest, "std_data_root"),
    "lpatchtst": (run_lpatchtst_backtest, "std_data_root"),
    "lstm": (run_lstm_backtest, "std_data_root"),
    "patchtst": (run_patchtst_backtest, "std_data_root"),
    "tft": (run_tft_backtest, "std_data_root"),
    "tips_regime_aware_transformer": (run_tips_backtest, "std_data_root"),
    "regime_analysis": (run_per_bar_regime_backtest, "bars_time_format"),
    "trend_lifecycle": (run_signal_outcome_backtest, "bars_time_format"),
    "shock_personality": (run_shock_backtest, "bars_time_format"),
    "shock_clustering": (run_shock_date_backtest, "bars_only"),
    "news_price_causality_impact": (run_impact_backtest, "bars_articles"),
    "news_price_causality_aggregate": (run_aggregate_tests_backtest, "bars_articles"),
    "peer_relative_strength": (run_relative_strength_backtest, "bars_price_client"),
    "peer_relative_strength_forward_validation": (run_forward_return_validation, "bars_price_client"),
    "trend_session_structure": (_run_trend_session_structure_chained, "bars_time_format"),
    "pnl_attribution": (aggregate_pnl_attribution, "positions"),
}


def build_work_fn(
    angle_name: str,
    symbol: str,
    bars: pd.DataFrame,
    data_root: str,
    *,
    timeframe: str = "1D",
    articles: list[dict] | None = None,
    price_client: Any = None,
    positions: list[dict] | None = None,
) -> Callable[[], Any]:
    """Returns a zero-arg callable for run_batch()'s work_fn, calling
    `angle_name`'s real backtest entry point with the right positional
    shape for that angle. Raises KeyError for an angle not yet in the
    registry (see the module docstring for what's excluded and why)."""
    run_fn, shape = ANGLE_REGISTRY[angle_name]
    if shape == "std":
        return lambda: run_fn(symbol, timeframe, bars)
    if shape == "std_data_root":
        return lambda: run_fn(symbol, timeframe, bars, data_root)
    if shape == "bars_time_format":
        # time_format passed by KEYWORD, not positionally -- real bug
        # found this way: shock_personality's real 3rd positional param
        # is `news`, not `time_format` (which is 4th there), so a
        # positional call silently passed the timeframe string into the
        # news slot and blew up inside the angle with an unrelated
        # AttributeError. regime_analysis/trend_lifecycle both happen to
        # have time_format 3rd, so this was invisible for them -- keyword
        # calling is correct and safe for all three regardless of position.
        return lambda: run_fn(symbol, bars, time_format=timeframe)
    if shape == "bars_only":
        return lambda: run_fn(symbol, bars)
    if shape == "bars_articles":
        if articles is None:
            raise ValueError(
                f"{angle_name!r} requires real articles (list[dict]) -- pass "
                "news_repository=... to build_batch_jobs()"
            )
        candles = bars.to_dict(orient="records")
        return lambda: run_fn(symbol, candles, articles)
    if shape == "bars_price_client":
        if price_client is None:
            raise ValueError(
                f"{angle_name!r} requires a real price_client -- pass "
                "price_client=... to build_batch_jobs()"
            )
        return lambda: run_fn(symbol, bars, price_client=price_client)
    if shape == "positions":
        # positions=[] is a real, valid state (a symbol with no real
        # closed trades yet -- the angle's own honest "no_data" row), so
        # only `None` (positions_by_symbol never supplied at all) errors.
        if positions is None:
            raise ValueError(
                f"{angle_name!r} requires real positions (list[dict], [] is "
                "fine) -- pass positions_by_symbol=... to build_batch_jobs()"
            )
        return lambda: run_fn(symbol, positions)
    raise ValueError(f"unknown call shape {shape!r} for angle {angle_name!r}")  # pragma: no cover


def build_batch_jobs(
    symbols: list[str],
    bars_by_symbol: dict[str, pd.DataFrame],
    data_root: str,
    *,
    angle_names: list[str] | None = None,
    timeframe: str = "1D",
    news_repository: Any = None,
    articles_from_ts: int | None = None,
    articles_to_ts: int | None = None,
    price_client: Any = None,
    positions_by_symbol: dict[str, list[dict]] | None = None,
) -> list[tuple[str, str, Callable[[], Any]]]:
    """Builds (symbol, angle_name, work_fn) tuples for run_batch() --
    every angle in `angle_names` (default: every registered angle) times
    every symbol in `symbols`.

    `news_repository` (e.g. a real `vinu_news.analysis.storage.repository.
    NewsRepository`) is required to include either `bars_articles`-shaped
    angle (`news_price_causality_impact`/`_aggregate`) -- real articles are
    fetched once per symbol (cached across angles needing them in the same
    batch) via `news_repository.get_news_for_ticker(symbol, start_ts=...,
    end_ts=...)`.

    `price_client` (either the real HTTP `clients.price_client.PriceClient`
    or the local, no-server `clients.local_price_client.LocalPriceClient`)
    is required to include either `bars_price_client`-shaped angle
    (`peer_relative_strength`/`_forward_validation`).

    `positions_by_symbol` (e.g. built from real
    `vinu_live.book.positions.list_closed_positions(book_backend,
    symbol=...)` per symbol) is required to include `pnl_attribution`.
    A symbol missing from the dict is treated as `[]` (no real closed
    trades for it yet), not an error -- `pnl_attribution` already handles
    that as its own honest `status: "no_data"` row."""
    names = angle_names if angle_names is not None else list(ANGLE_REGISTRY)
    jobs: list[tuple[str, str, Callable[[], Any]]] = []
    articles_cache: dict[str, list[dict]] = {}
    for symbol in symbols:
        bars = bars_by_symbol[symbol]
        for angle_name in names:
            _, shape = ANGLE_REGISTRY[angle_name]
            articles = None
            positions = None
            if shape == "bars_articles":
                if news_repository is None:
                    raise ValueError(
                        f"{angle_name!r} requires news_repository to be "
                        "passed to build_batch_jobs()"
                    )
                if symbol not in articles_cache:
                    articles_cache[symbol] = news_repository.get_news_for_ticker(
                        symbol, start_ts=articles_from_ts, end_ts=articles_to_ts,
                    )
                articles = articles_cache[symbol]
            if shape == "positions":
                if positions_by_symbol is None:
                    raise ValueError(
                        f"{angle_name!r} requires positions_by_symbol to be "
                        "passed to build_batch_jobs()"
                    )
                positions = positions_by_symbol.get(symbol, [])
            work_fn = build_work_fn(
                angle_name, symbol, bars, data_root,
                timeframe=timeframe, articles=articles, price_client=price_client,
                positions=positions,
            )
            jobs.append((symbol, angle_name, work_fn))
    return jobs


# -- parallel-batch harness integration -------------------------------------
#
# The 7 angles below all pass a fixed window=MIN_OBSERVATIONS to their own
# real walk-forward loop (see parallel-backtest-infra.md's group split), so
# their real StepFn/min_observations/window/horizon can be run through
# run_walk_forward_parallel_batch() directly -- ONE shared process pool
# across every (symbol, angle) job here, not each job's own run_*_backtest()
# spinning up (and tearing down) its own pool, which measured WORSE than
# plain sequential (fresh-pool-per-call tax paid repeatedly, see that doc's
# "Measured numbers" section). This is the actual lever
# 03-still-open-not-wired.md's deferral was waiting on a real batch to
# justify -- run_batch_with_parallel_harness below is that real batch.
PARALLEL_SAFE_ANGLES: frozenset[str] = frozenset({
    "arima", "chronos", "exponential_smoothing", "garch",
    "kalman_filters", "kronos", "timer_timerxl",
})

# angle_name -> (step_fn builder (takes timeframe, returns a real
# module-level StepFn -- garch's own step needs timeframe bound via
# functools.partial, same as its own run_garch_backtest does; the other 6
# ignore the argument and return their own already-module-level step_fn
# directly), min_observations, window, horizon).
_PARALLEL_STEP_CONFIG: dict[str, tuple[Callable[[str], Callable], int, int, int]] = {
    "arima": (lambda tf: arima_step, _ARIMA_MIN_OBS, _ARIMA_MIN_OBS, 1),
    "chronos": (lambda tf: chronos_step, _CHRONOS_MIN_OBS, _CHRONOS_MIN_OBS, _CHRONOS_HORIZON),
    "exponential_smoothing": (lambda tf: es_step, _ES_MIN_OBS, _ES_MIN_OBS, 1),
    "garch": (
        lambda tf: functools.partial(_garch_step, timeframe=tf),
        _GARCH_MIN_OBS, _GARCH_MIN_OBS, 1,
    ),
    "kalman_filters": (lambda tf: kalman_step, _KALMAN_MIN_OBS, _KALMAN_MIN_OBS, 1),
    "kronos": (lambda tf: kronos_step, _KRONOS_MIN_OBS, _KRONOS_MIN_OBS, _KRONOS_HORIZON),
    "timer_timerxl": (lambda tf: timer_timerxl_step, _TIMER_MIN_OBS, _TIMER_MIN_OBS, _TIMER_HORIZON),
}


def build_walk_forward_jobs(
    symbols: list[str],
    bars_by_symbol: dict[str, pd.DataFrame],
    *,
    angle_names: list[str] | None = None,
    timeframe: str = "1D",
    chunk_size: int = 200,
) -> list[WalkForwardJob]:
    """Real WalkForwardJob objects for the parallel-safe angles (see
    PARALLEL_SAFE_ANGLES), for run_walk_forward_parallel_batch(). Any
    angle_name not in PARALLEL_SAFE_ANGLES is silently skipped -- callers
    that want a mixed batch should filter angle_names themselves (see
    run_batch_with_parallel_harness, which does exactly that split).
    `key` on each job is f"{symbol}:{angle_name}", the same convention
    run_batch()/build_batch_jobs() use, so results from both paths merge
    under one consistent key scheme."""
    names = [a for a in (angle_names or sorted(PARALLEL_SAFE_ANGLES)) if a in PARALLEL_SAFE_ANGLES]
    jobs: list[WalkForwardJob] = []
    for symbol in symbols:
        bars = bars_by_symbol[symbol]
        for angle_name in names:
            step_builder, min_observations, window, horizon = _PARALLEL_STEP_CONFIG[angle_name]
            jobs.append(WalkForwardJob(
                key=f"{symbol}:{angle_name}",
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                step_fn=step_builder(timeframe),
                min_observations=min_observations,
                window=window,
                horizon=horizon,
                tag_fn=tag_row,
                chunk_size=chunk_size,
            ))
    return jobs


def _persist_result_and_write_factsheet(
    storage: AngleStorage,
    run_log: RunLog,
    data_root: str,
    symbol: str,
    angle_name: str,
    timeframe: str,
    df: Any,
    *,
    tier: str = "tier2",
) -> None:
    """Real storage/RunLog write for one job's result, then a fresh fact
    sheet for it -- the file being "there right after the angle runs"
    requires this batch path to actually persist, which (unlike
    runner.py's separate compute() path) it did not do before this: a
    plain run_batch()/run_batch_with_parallel_harness() call only ever
    returned DataFrames in memory. Skips anything that isn't a real,
    non-empty result (e.g. a job whose own step_fn already reported
    "fit_failed" as a status row is still real data and gets persisted;
    None/empty means nothing to persist)."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    run_id = uuid4().hex[:12]
    t0 = time.perf_counter()
    # Real analysis_from/analysis_until, derived from this run's own real
    # bar_ts values -- not a shared config value, since different angles
    # in the same batch can (and do -- see chronos/kronos, news_price_
    # causality) use a different real window. AngleStorage.write()'s
    # analysis_from/analysis_until columns existed in the schema before
    # this but were never populated by this batch path (confirmed: always
    # NaT in every real run so far) -- the fact sheet worked around this
    # by deriving its "Real data covers X to Y" line straight from bar_ts
    # each time instead, but the dedicated storage slot for it sat unused.
    analysis_from = analysis_until = None
    if "bar_ts" in df.columns:
        real_ts = pd.to_numeric(df["bar_ts"], errors="coerce").dropna()
        if not real_ts.empty:
            analysis_from = int(real_ts.min())
            analysis_until = int(real_ts.max())
    storage.write(
        symbol, angle_name, df, run_id=run_id, granularity=timeframe, tier=tier,
        analysis_from=analysis_from, analysis_until=analysis_until,
    )
    run_log.record_run(
        symbol=symbol,
        angle_name=angle_name,
        run_id=run_id,
        row_count=len(df),
        granularity=timeframe,
        tier=tier,
        duration_seconds=time.perf_counter() - t0,
    )
    write_factsheet(data_root, symbol, angle_name, run_log, storage, tier=tier)


def run_batch_with_parallel_harness(
    tracker: AngleRunStatus,
    batch_id: str,
    symbols: list[str],
    bars_by_symbol: dict[str, pd.DataFrame],
    data_root: str,
    *,
    angle_names: list[str] | None = None,
    timeframe: str = "1D",
    max_attempts: int = 3,
    n_workers: int | None = None,
    chunk_size: int = 200,
    min_total_steps_for_parallel: int = 1500,
    news_repository: Any = None,
    articles_from_ts: int | None = None,
    articles_to_ts: int | None = None,
    price_client: Any = None,
    positions_by_symbol: dict[str, list[dict]] | None = None,
    run_log: RunLog | None = None,
    tier: str = "tier2",
) -> dict[str, Any]:
    """Same real contract as orchestration.run_batch (every job registered
    up front for full visibility, batch rows deleted only once every job
    succeeds) -- but the 7 PARALLEL_SAFE_ANGLES jobs run through ONE shared
    run_walk_forward_parallel_batch() process pool instead of each one's
    own sequential work_fn() call. Every other angle in `angle_names`
    (default: every registered angle) still runs through the existing
    sequential per-job loop (via run_batch), unchanged.

    Real numbers this split is based on (parallel-backtest-infra.md): a
    single job's own fresh process pool measured essentially no gain
    (1.02x) or even a net loss when paid per-call -- the win only shows up
    once enough real work shares ONE pool (measured 1.26-1.34x on a real
    3-symbol/1-angle batch). Splitting one shared pool across all 7
    parallel-safe angles x every symbol in one call is the same lever at
    real orchestrator scale, not per single-angle call.

    `run_log`: opt-in. When given, every job that actually succeeds with a
    real, non-empty result is written through AngleStorage/RunLog for
    real, and a fresh fact sheet (`storage/factsheet.py`) is written to
    `{data_root}/factsheets/{symbol}/{angle_name}.md` right after -- this
    is what makes the file "there" once an angle has run. When omitted
    (the default), behavior is unchanged from before: results are
    returned in memory only, nothing is written to disk beyond what the
    caller does itself -- every existing caller of this function keeps
    working exactly as before.
    """
    names = angle_names if angle_names is not None else list(ANGLE_REGISTRY)
    parallel_names = [a for a in names if a in PARALLEL_SAFE_ANGLES]
    sequential_names = [a for a in names if a not in PARALLEL_SAFE_ANGLES]

    all_job_keys = [(symbol, angle_name) for symbol in symbols for angle_name in names]
    tracker.register_batch(batch_id, all_job_keys, max_attempts=max_attempts)

    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if parallel_names:
        wf_jobs = build_walk_forward_jobs(
            symbols, bars_by_symbol, angle_names=parallel_names,
            timeframe=timeframe, chunk_size=chunk_size,
        )
        for symbol in symbols:
            for angle_name in parallel_names:
                tracker.mark_running(batch_id, symbol, angle_name)

        batch_result: BatchResult = run_walk_forward_parallel_batch(
            wf_jobs, n_workers=n_workers,
            min_total_steps_for_parallel=min_total_steps_for_parallel,
        )

        failures_by_key: dict[str, list[str]] = {}
        for failure in batch_result.failures:
            failures_by_key.setdefault(failure.key, []).append(
                f"[{failure.start_position},{failure.end_position}) "
                f"attempts={failure.attempts}: {failure.error}"
            )
        for symbol in symbols:
            for angle_name in parallel_names:
                key = f"{symbol}:{angle_name}"
                if key in failures_by_key:
                    error_msg = "; ".join(failures_by_key[key])
                    tracker.mark_failed(batch_id, symbol, angle_name, error_msg)
                    errors[key] = error_msg
                else:
                    results[key] = batch_result.data.get(key)
                    tracker.mark_ok(batch_id, symbol, angle_name)
                    if run_log is not None:
                        storage = AngleStorage(data_root, run_log=run_log)
                        _persist_result_and_write_factsheet(
                            storage, run_log, data_root, symbol, angle_name,
                            timeframe, results[key], tier=tier,
                        )

    if sequential_names:
        seq_jobs = build_batch_jobs(
            symbols, bars_by_symbol, data_root, angle_names=sequential_names,
            timeframe=timeframe, news_repository=news_repository,
            articles_from_ts=articles_from_ts, articles_to_ts=articles_to_ts,
            price_client=price_client, positions_by_symbol=positions_by_symbol,
        )
        # Reuses run_batch() exactly (register_batch's INSERT OR IGNORE
        # makes the already-registered parallel rows a harmless no-op
        # here) -- by the time run_batch's own is_batch_complete() check
        # runs, every row (parallel and sequential) already reflects its
        # true final status, so the batch's rows are only ever deleted
        # once, correctly, for the batch as a whole.
        seq_summary = run_batch(tracker, batch_id, seq_jobs, max_attempts=max_attempts)
        results.update(seq_summary["results"])
        errors.update(seq_summary["errors"])
        if run_log is not None:
            storage = AngleStorage(data_root, run_log=run_log)
            for key, df in seq_summary["results"].items():
                symbol, angle_name = key.split(":", 1)
                _persist_result_and_write_factsheet(
                    storage, run_log, data_root, symbol, angle_name, timeframe, df, tier=tier,
                )
    elif tracker.is_batch_complete(batch_id):
        tracker.delete_batch(batch_id)

    if run_log is not None:
        storage = AngleStorage(data_root, run_log=run_log)
        for symbol in symbols:
            write_summary(data_root, symbol, run_log, storage, angle_names=names, tier=tier)

    return {"results": results, "errors": errors, "ok": not errors}
