"""`RankerRunner`: the glue between a `RankerConfig` and B10's
`ScreenPipeline` -- fetches OHLCV for the whole universe (via
`get_ohlcv_batch()` when the data source supports it, same one-call
preference `ScanMonitor` uses), computes every configured `FactorSpec` via
B5's `IndicatorFactory` (one broadcast call per factor across the whole
universe, not one call per symbol per factor), builds the per-symbol
`fields` dict `ScreenPipeline` expects, and runs it.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..features.factory import IndicatorFactory
from ..features.library import FeatureLibrary
from ..pipeline.pipeline import PipelineConfig, PipelineResult, ScreenPipeline
from ..pipeline.scorer import make_weighted_scorer
from ..scan.data_source import SymbolDataSource
from .config import RankerConfig


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
        for symbol, df in ohlcv.items():
            last = df.iloc[-1]
            price = float(last["close"])
            volume = float(last["volume"])
            snapshots[symbol].setdefault("price", price)
            snapshots[symbol].setdefault("volume", volume)
            snapshots[symbol].setdefault("dollar_volume", price * volume)

        scorer = make_weighted_scorer(cfg.factors)
        pipeline = ScreenPipeline(scorer, PipelineConfig(top_n=cfg.top_n, hard_filter=cfg.hard_filter))
        return pipeline.run(snapshots, seed=seed, sectors=sectors, enrich_fn=enrich_fn)
