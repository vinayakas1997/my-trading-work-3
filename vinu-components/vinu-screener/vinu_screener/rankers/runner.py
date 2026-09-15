"""`RankerRunner`: the glue between a `RankerConfig` and B10's
`ScreenPipeline` -- fetches OHLCV for the whole universe (via
`get_ohlcv_batch()` when the data source supports it, same one-call
preference `ScanMonitor` uses), computes every configured `FactorSpec` via
B5's `IndicatorFactory` (one broadcast call per factor across the whole
universe, not one call per symbol per factor), builds the per-symbol
`fields` dict `ScreenPipeline` expects, and runs it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..features.factory import IndicatorFactory
from ..features.library import FeatureLibrary
from ..pipeline.pipeline import PipelineConfig, PipelineResult, ScreenPipeline
from ..pipeline.scorer import make_weighted_scorer
from ..scan.data_source import SymbolDataSource
from .config import RankerConfig

# A fresh daily bar should be at most a couple of trading days old (weekend
# gap included). risk_overlay.py's `stale_data`/`fetch_degraded` checks
# (DEFAULT_RISK_CHECKS) have existed since B12 -- "a candidate built from
# degraded data is itself a risk" -- but nothing has ever set the
# `data_stale`/`data_fetch_degraded` fields they read: every candidate
# scored identically to one built from good data regardless of what
# actually happened during the fetch (see high-expectations gate-conflict
# audit). Fail-open on the age check itself (an unparseable index age is
# not evidence of staleness).
STALE_DATA_MAX_AGE_DAYS = 3


def _is_stale(df: pd.DataFrame, max_age_days: int = STALE_DATA_MAX_AGE_DAYS) -> bool:
    try:
        last_ts = df.index[-1]
        if getattr(last_ts, "tzinfo", None) is None:
            last_ts = last_ts.tz_localize("UTC")
        age = datetime.now(timezone.utc) - last_ts.to_pydatetime()
        return age.total_seconds() > max_age_days * 86400
    except Exception:
        return False


class RankerRunner:
    def __init__(self, data_source: SymbolDataSource, *, library: FeatureLibrary | None = None) -> None:
        self._data_source = data_source
        self._library = library or FeatureLibrary()
        self._factory = IndicatorFactory(self._library)

    def _fetch_universe(self, symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
        if hasattr(self._data_source, "get_ohlcv_batch"):
            batch = self._data_source.get_ohlcv_batch(list(symbols))
            return {s: df for s, df in batch.items() if df is not None and not df.empty}
        out: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            df = self._data_source.get_ohlcv(symbol)
            if df is not None and not df.empty:
                out[symbol] = df
        return out

    def run(
        self,
        cfg: RankerConfig,
        *,
        seed: int = 0,
        sectors: dict[str, str] | None = None,
        enrich_fn: Any = None,
        held_symbols: frozenset[str] | None = None,
    ) -> PipelineResult:
        ohlcv = self._fetch_universe(cfg.universe)
        self._library.clear_cache()

        snapshots: dict[str, dict[str, float]] = {symbol: {} for symbol in ohlcv}
        for factor in cfg.factors:
            values = self._factory.latest(
                factor.indicator, ohlcv, factor.params, field=factor.output_field, offset=factor.offset,
            )
            for symbol, value in values.items():
                snapshots[symbol][factor.name] = value

        # Always carry price/volume/dollar_volume -- HardFilterConfig's own
        # bounds read these field names regardless of what factors a ranker
        # happens to configure, and they're nearly free (one bar already
        # fetched) to include unconditionally.
        #
        # data_stale/data_fetch_degraded feed risk_overlay.py's DEFAULT_RISK_
        # CHECKS (stale_data/fetch_degraded, 10pt penalty each) -- see this
        # module's own STALE_DATA_MAX_AGE_DAYS docstring for why these were
        # dead code before. last_batch_failed_symbols is the same signal
        # ScanMonitor already reads for a different purpose (see scan/
        # monitor.py's own use of it); it can never actually be set for a
        # symbol present here under HttpStockDataSource's current
        # all-or-nothing batch-chunk semantics, but is wired for real
        # (rather than left unset) so a SymbolDataSource that CAN report a
        # present-but-degraded fetch (e.g. a fallback provider) is honored.
        failed_symbols = {
            s.upper() for s in getattr(self._data_source, "last_batch_failed_symbols", None) or ()
        }
        held = {s.upper() for s in (held_symbols or ())}
        for symbol, df in ohlcv.items():
            last = df.iloc[-1]
            price = float(last["close"])
            volume = float(last["volume"])
            snapshots[symbol].setdefault("price", price)
            snapshots[symbol].setdefault("volume", volume)
            snapshots[symbol].setdefault("dollar_volume", price * volume)
            snapshots[symbol]["data_stale"] = 1.0 if _is_stale(df) else 0.0
            snapshots[symbol]["data_fetch_degraded"] = 1.0 if symbol.upper() in failed_symbols else 0.0
            # Held-symbol awareness: feeds risk_overlay.py's already_held
            # RiskCheck, same pattern as data_stale/data_fetch_degraded
            # above. held_symbols is empty unless a caller explicitly
            # fetched real positions (see RankerScheduler's
            # held_symbols_fetcher) -- ships inert otherwise.
            snapshots[symbol]["already_held"] = 1.0 if symbol.upper() in held else 0.0

        scorer = make_weighted_scorer(cfg.factors)
        pipeline = ScreenPipeline(scorer, PipelineConfig(top_n=cfg.top_n, hard_filter=cfg.hard_filter))
        return pipeline.run(snapshots, seed=seed, sectors=sectors, enrich_fn=enrich_fn)
