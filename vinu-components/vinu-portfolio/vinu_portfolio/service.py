from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np
import pandas as pd
import yaml

from vinu_infra.ticker_profile import write_ticker_profile_key
from vinu_portfolio.config import PortfolioConfig, load_config
from vinu_portfolio.game_plan import DailyGamePlan, SymbolPlan
from vinu_portfolio.regime import classify_current_regime
from vinu_portfolio.risk_budget import compute_risk_budget, DailyPositionTracker
from vinu_portfolio.risk_utils import (
    cap_concentration,
    hrp_weights,
    rescale_correlated_clusters,
    robust_correlation_matrix,
)
from vinu_portfolio.shock_correlation import dcc_shock_correlation
from vinu_portfolio.sizing import apply_position_sizing
from vinu_portfolio.storage.drawdown_status import DrawdownStatusStore

LOG = logging.getLogger(__name__)


def _record_edge(edge_id: str, status: str, detail: str = "") -> None:
    """Observe-only pipeline-edge recording (vinu_infra.pipeline_edge_recorder); never raises, never affects the caller."""
    try:
        from vinu_infra.pipeline_edge_recorder import record_edge

        record_edge(edge_id, status, detail)
    except Exception:  # noqa: BLE001
        pass

# regime_analysis's own labels (bull/bear/high_vol/sideways, see
# vinu_portfolio/regime.py) vs. strategy-tags/tags.yaml's labels (trending/
# ranging/mean_reverting) are two different, unreconciled vocabularies in
# this codebase -- confirmed by reading tags.yaml itself, whose per-strategy
# notes already reference regime_analysis.regime == "bear"/"sideways"/
# "high_vol" directly inside each strategy's own signal-zeroing logic, a
# vocabulary tags.yaml's own `regime:` field never uses. bull/bear both
# plausibly read as "trending" (tags.yaml doesn't encode direction);
# high_vol has no direction-based tag equivalent, and every one of the 4
# tagged strategies already zeros or cuts its own signal under high_vol
# internally -- so this tilt deliberately stays neutral for high_vol rather
# than double-penalizing on top of that existing suppression.
_REGIME_TO_TAGS: dict[str, set[str]] = {
    "bull": {"trending"},
    "bear": {"trending"},
    "sideways": {"ranging", "mean_reverting"},
}


class PortfolioService:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self._config = config or load_config()
        try:
            from vinu_infra.auth import internal_auth_headers
            _headers = internal_auth_headers() or None
        except Exception:
            _headers = None
        self._http = httpx.AsyncClient(timeout=10.0, headers=_headers)
        self._tags_cache: dict[str, Any] | None = None
        # J: per-cycle returns cache to avoid double fetch of same equity series
        # (build_portfolio + allocate_risk_parity both called _build_returns_df)
        self._returns_cache: dict[str, tuple[float, pd.Series]] = {}
        self._returns_cache_ttl = 60.0
        # Perf: build_portfolio()'s own derived output (corr matrix, HRP/
        # risk-parity weights, DCC shock correlation) was recomputed from
        # scratch on every call -- even when the underlying returns are
        # still the fresh ones sitting in _returns_cache above. vinu-live
        # polls /portfolio/state every cycle, and compute_risk_status's own
        # call chain (-> compute_daily_game_plan -> compute_daily_allocation)
        # calls build_portfolio() again on top of that, so the same
        # correlation/HRP/DCC pipeline ran multiple times per second for
        # identical inputs. Keyed on the resolved strategy set (name +
        # artifact_id + is_candidate for every strategy/candidate actually
        # passed into the pipeline) so a different evaluate-batch candidate
        # set, or a strategy activating/deactivating, gets a fresh
        # computation; same TTL as the returns cache above since a cached
        # entry can never outlive the returns data it was built from.
        self._portfolio_cache: dict[tuple, tuple[float, dict[str, Any]]] = {}
        self._portfolio_cache_ttl = 60.0
        # Hysteresis (19 step3): last tilted weights, no flip-flop on noise.
        self._last_weights: dict[str, float] = {}
        # Stage 2 (how-to-make-it-live.md #22): DailyPositionTracker must live
        # on the service instance, not be created fresh inside
        # compute_risk_status() -- a fresh tracker every call meant
        # record_daily_pnl() always started from zero, so tier/halted status
        # never accumulated across a real trading day. _service in
        # server/app.py is constructed once and reused across requests, so
        # this now actually persists for the process lifetime (resets at UTC
        # midnight via DailyPositionTracker's own _check_reset()).
        self._risk_tracker = DailyPositionTracker()
        # Dated allocation history -- vinu-portfolio's first piece of
        # persistent storage of its own; see storage/allocation_history.py.
        from vinu_portfolio.storage.allocation_history import AllocationHistoryStore
        self._allocation_history = AllocationHistoryStore(self._config.data_root / "allocation_history.db")
        # item #23 findings #2/#3 (system-wide-audit-and-design/
        # 02-open-questions-strategy-and-simulation.md): cross-process
        # read of the drawdown monitor's real halve/flat/halt state -- see
        # drawdown_status.py's own docstring for why this can't just be an
        # in-memory read.
        self._drawdown_status_store = DrawdownStatusStore(self._config.data_root / "drawdown_status.db")

    async def close(self) -> None:
        await self._http.aclose()
        self._allocation_history.close()
        self._drawdown_status_store.close()

    async def __aenter__(self) -> PortfolioService:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Strategy inventory — pulls ACTIVE strategies from both mechanisms
    # ------------------------------------------------------------------

    async def list_active_strategies(self) -> list[dict[str, Any]]:
        """Unified list of all ACTIVE strategies across both mechanisms.

        Returns:
          [
            {"name": ..., "kind": "yaml"|"llm_python", "symbol": ..., "weights_source": ...},
            ...
          ]
        """
        yaml_strategies, llm_strategies = await asyncio.gather(
            self._list_yaml_strategies(),
            self._list_llm_strategies(),
            return_exceptions=True,
        )
        strategies: list[dict[str, Any]] = []
        if isinstance(yaml_strategies, list):
            strategies.extend(yaml_strategies)
        else:
            LOG.warning("Failed to list YAML strategies: %s", yaml_strategies)
        if isinstance(llm_strategies, list):
            strategies.extend(llm_strategies)
        else:
            LOG.warning("Failed to list LLM strategies: %s", llm_strategies)
        return strategies

    async def _list_yaml_strategies(self) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._config.strategy_api_url}/strategy/strategies")
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return [
            {
                "name": s.get("name", "unknown"),
                "kind": "yaml",
                "symbol": s.get("symbol", s.get("ticker", "")),
                "weights_source": f"{self._config.strategy_api_url}/strategy/weights/{s.get('name', '')}",
                # YAML registry strategies are all schedule:daily -- see the
                # interval_sleeves comment in compute_daily_allocation.
                "timeframe": "daily",
            }
            for s in data
        ]

    async def _list_llm_strategies(self) -> list[dict[str, Any]]:
        """In-process first (reads vinu-research's real local strategy_store
        directly), HTTP fallback only if that raises -- see
        vinu_portfolio/research_link.py. Found while migrating: this
        codebase has its own independent HTTP dependency on vinu-research,
        separate from vinu-agent's -- not covered by the original
        vinu-research-in-process migration doc at all."""
        try:
            data = await self._list_llm_strategies_in_process()
        except Exception as e:
            LOG.debug("Failed in-process ACTIVE-artifact read, falling back to HTTP: %s", e)
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/artifacts",
                params={"status": "ACTIVE"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {
                "name": a.get("name", "unknown"),
                "kind": "llm_python",
                "symbol": a.get("universe", [""])[0] if a.get("universe") else "",
                "artifact_id": a.get("artifact_id", ""),
                "weights_source": f"artifact:{a.get('artifact_id', '')}",
                # Stage 2 (how-to-make-it-live.md #34): confidence-gradient
                # sizing needs the promotion margin, not just pass/fail.
                "deflated_sharpe": a.get("deflated_sharpe", 0.0),
                "timeframe": a.get("timeframe", "daily"),
            }
            for a in data
        ]

    async def _list_llm_strategies_in_process(self) -> list[dict[str, Any]]:
        from vinu_portfolio.research_link import get_strategy_store
        from vinu_research.models import ArtifactStatus

        store = get_strategy_store()
        artifacts = await asyncio.to_thread(store.list_artifacts_by_statuses, [ArtifactStatus.ACTIVE])
        return [
            {
                "name": a.name, "artifact_id": a.artifact_id, "universe": a.universe,
                "deflated_sharpe": a.deflated_sharpe, "timeframe": a.timeframe,
            }
            for a in artifacts
        ]

    # ------------------------------------------------------------------
    # Correlation matrix across strategies
    # ------------------------------------------------------------------

    async def compute_correlation_matrix(
        self, strategies: list[dict[str, Any]]
    ) -> pd.DataFrame | None:
        """Fetch historical returns for each strategy and compute correlation.

        Stage A (A1/A2): hardened via risk_utils.robust_correlation_matrix
        (Ledoit-Wolf shrinkage + spectral PSD repair) instead of a raw
        returns_df.corr() -- see that module's docstring for why a raw
        sample correlation from limited history is risky to feed straight
        into a pass/fail decision downstream.
        """
        returns_df = await self._build_returns_df(strategies)
        return robust_correlation_matrix(returns_df)

    async def _build_returns_df(
        self, strategies: list[dict[str, Any]]
    ) -> pd.DataFrame | None:
        """Fetch historical daily-returns series for each strategy, aligned into one frame.

        Shared by compute_correlation_matrix (needs df.corr()) and build_portfolio
        (needs the raw returns for allocate_risk_parity's vol calc) so both are
        derived from the same fetch instead of one deriving vol from the other's
        correlation output.
        """
        returns_data: dict[str, pd.Series] = {}
        for s in strategies:
            returns = await self._fetch_strategy_returns(s)
            if returns is not None and len(returns) >= 10:
                returns_data[s["name"]] = returns

        if len(returns_data) < 2:
            LOG.info("Need at least 2 strategies with return data for correlation")
            return None

        return pd.DataFrame(returns_data)

    async def _fetch_strategy_returns(self, strategy: dict[str, Any]) -> pd.Series | None:
        """Fetch daily returns series for a strategy. J: cached 60s to avoid double fetch."""
        import time as _time
        cache_key = strategy.get("artifact_id") or strategy.get("name", "")
        if cache_key and cache_key in self._returns_cache:
            ts, cached = self._returns_cache[cache_key]
            if _time.time() - ts < self._returns_cache_ttl:
                return cached
        try:
            if strategy["kind"] == "yaml":
                resp = await self._http.get(strategy["weights_source"])
                if resp.status_code != 200:
                    return None
                weights = resp.json()
                if isinstance(weights, list) and weights:
                    series = pd.Series(
                        [float(w.get("weight", 0)) for w in weights],
                        index=pd.to_datetime([w.get("date") for w in weights]),
                    )
                    ret = series.pct_change().dropna()
                    if cache_key:
                        self._returns_cache[cache_key] = (_time.time(), ret)
                    return ret
            elif strategy["kind"] == "llm_python":
                artifact_id = strategy.get("artifact_id", "")
                resp = await self._http.get(
                    f"{self._config.simulator_api_url}/simulator/results/{artifact_id}/equity"
                )
                if resp.status_code != 200:
                    return None
                data: list[dict] = resp.json()
                if data and len(data) >= 2:
                    series = pd.Series(
                        [float(r.get("portfolio_value", 0)) for r in data],
                        index=pd.to_datetime([r.get("date") for r in data]),
                    )
                    ret2 = series.pct_change().dropna()
                    if cache_key:
                        import time as _time2
                        self._returns_cache[cache_key] = (_time2.time(), ret2)
                    return ret2
        except Exception as e:
            LOG.warning("Failed to fetch returns for %s: %s", strategy.get("name"), e)
        return None

    # ------------------------------------------------------------------
    # Capital allocation — risk-parity (inverse-vol weighting)
    # ------------------------------------------------------------------

    def allocate_risk_parity(
        self,
        strategies: list[dict[str, Any]],
        returns_df: pd.DataFrame | None = None,
    ) -> list[dict[str, Any]]:
        """Inverse-volatility risk-parity allocation.

        Each strategy gets weight proportional to 1/vol. Falls back to
        equal-weight when vol data is unavailable.

        Which of these two runs is `PortfolioConfig.allocation_mode`: the DEFAULT is
        "hrp" (hierarchical risk parity, correlation-aware; for two assets it splits
        by inverse VARIANCE, so a strategy with half the volatility gets 4:1, not 2:1);
        "inverse_vol" is the plain 1/vol rule described above. Both worked out by hand
        in tests/test_logic_allocation_by_hand.py.
        """
        if not strategies:
            return []

        weights: dict[str, float] = {}
        # Annualized vol per strategy, kept alongside the weight it produced
        # so a caller can see *why* a strategy got a small allocation, not
        # just the resulting number. Computed whenever returns_df has the
        # column, regardless of which branch below actually set the weight
        # (HRP still wants this for its own inputs).
        vol_by_name: dict[str, float] = {}
        if returns_df is not None and len(returns_df.columns) >= 1:
            vol_series = returns_df.std() * np.sqrt(252)
            vol_by_name = vol_series.to_dict()

        # Stage C (C11): HRP mode — correlation-aware, inversion-free. Falls
        # back to inverse-vol below when there isn't enough history to
        # cluster (hrp_weights returns None).
        if getattr(self._config, "allocation_mode", "inverse_vol") == "hrp":
            hrp = hrp_weights(returns_df)
            if hrp is not None:
                for s in strategies:
                    weights[s["name"]] = hrp.get(s["name"], 1.0 / len(strategies))

        if not weights and returns_df is not None and len(returns_df.columns) >= 1:
            vols = returns_df.std() * np.sqrt(252)
            inv_vols = 1.0 / vols.clip(lower=1e-6)
            total = inv_vols.sum()
            if total > 0:
                raw_weights = (inv_vols / total).to_dict()
                for s in strategies:
                    weights[s["name"]] = raw_weights.get(s["name"], 1.0 / len(strategies))
            else:
                for s in strategies:
                    weights[s["name"]] = 1.0 / len(strategies)
        elif not weights:
            for s in strategies:
                weights[s["name"]] = 1.0 / len(strategies)

        total_weight = sum(weights.values())
        if total_weight > 0:
            for k in weights:
                weights[k] /= total_weight

        # Stage A (A4): enforce the per-strategy cap AFTER normalization,
        # via cap_concentration's iterative redistribute -- the old
        # `min(w, cap)` was applied BEFORE the normalize above, which
        # renormalization then undid (a 0.30 cap could end up at 0.75; see
        # cap_concentration's docstring). This is the one place the cap
        # actually binds now.
        weights = cap_concentration(weights, self._config.max_per_strategy_weight)

        result = []
        for s in strategies:
            result.append({
                "name": s["name"],
                "kind": s["kind"],
                "symbol": s.get("symbol", ""),
                "target_weight": round(weights.get(s["name"], 0.0), 4),
                # artifact_id/is_candidate: carried through (not computed
                # here) so a caller evaluating a mixed batch -- the real
                # ACTIVE book plus vinu-agent's Phase 2 PEND candidates --
                # can map a weight back to the specific candidate it funds,
                # not just match by name string.
                "artifact_id": s.get("artifact_id", ""),
                "is_candidate": bool(s.get("is_candidate", False)),
                "vol_annualized": (
                    round(vol_by_name[s["name"]], 4) if s["name"] in vol_by_name else None
                ),
            })
        return result

    # ------------------------------------------------------------------
    # Full portfolio construction pipeline
    # ------------------------------------------------------------------

    async def build_portfolio(
        self, extra_candidates: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Run the full portfolio construction pipeline.

        1. List active strategies (YAML + LLM)
        2. Compute correlation matrix
        3. Risk-parity allocation
        4. Apply constraints

        Returns the portfolio weights and metadata.

        `extra_candidates` (vinu-agent Phase 2 -- capital_allocator's PEND
        batch, see New-talk-agents/new-thinking/new-restructure/phases/
        phase-2-funding-mechanics/): additional strategy dicts, same shape
        as list_active_strategies()'s own output plus `is_candidate=True`,
        evaluated ALONGSIDE the real active book in the same correlation/
        risk-parity pass. This is how a PEND artifact's would-be weight and
        its correlation with the existing book (and with other PEND
        candidates in the same batch) get computed WITHOUT it needing to
        already be ACTIVE -- list_active_strategies() only ever returns
        ACTIVE artifacts (confirmed: _list_llm_strategies() filters
        `status=ACTIVE` server-side), so a PEND candidate is otherwise
        invisible to this pipeline entirely. Every existing no-arg caller
        (build_portfolio() with nothing passed) is unaffected.
        """
        strategies = await self.list_active_strategies()
        if extra_candidates:
            strategies = strategies + extra_candidates
        if not strategies:
            return {"status": "empty", "strategies": [], "weights": [], "matrix": None}

        import time as _time

        cache_key = tuple(sorted(
            (s.get("name", ""), s.get("artifact_id", ""), bool(s.get("is_candidate", False)))
            for s in strategies
        ))
        cached = self._portfolio_cache.get(cache_key)
        if cached and _time.time() - cached[0] < self._portfolio_cache_ttl:
            return cached[1]

        returns_df = await self._build_returns_df(strategies)
        # Stage A (A1/A2): same hardened path as compute_correlation_matrix
        # -- this was previously its own separate raw returns_df.corr()
        # call, computing the same thing twice with two different levels
        # of trustworthiness. This is the correlation matrix OrderGuard's
        # pairwise-correlation concentration check (order_guard.py's
        # _check_portfolio_concentration, via GET /portfolio/state) acts
        # on for real orders.
        corr_matrix = robust_correlation_matrix(returns_df)

        weights = self.allocate_risk_parity(strategies, returns_df)

        # Stage C (C12): post-construction rescaling over the whole target
        # set -- cap the combined weight of any correlated cluster no
        # single-name check would catch. Opt-in (max_correlated_cluster_weight
        # < 1.0); no-op otherwise. Runs on the same hardened corr matrix.
        if getattr(self._config, "max_correlated_cluster_weight", 1.0) < 1.0 and corr_matrix is not None:
            wmap = {w["name"]: w["target_weight"] for w in weights}
            rescaled = rescale_correlated_clusters(
                wmap, corr_matrix,
                corr_threshold=getattr(self._config, "cluster_corr_threshold", 0.8),
                max_cluster_weight=self._config.max_correlated_cluster_weight,
            )
            for w in weights:
                w["target_weight"] = round(rescaled.get(w["name"], w["target_weight"]), 4)

        matrix_dict: dict[str, Any] | None = None
        if corr_matrix is not None:
            matrix_dict = {
                "strategies": list(corr_matrix.columns),
                "values": corr_matrix.round(4).values.tolist(),
            }

        shock = dcc_shock_correlation(returns_df) if returns_df is not None else None

        composition = self._check_composition_gaps(weights, returns_df, corr_matrix)

        result = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_strategies": len(strategies),
            "strategies": strategies,
            "weights": weights,
            "correlation_matrix": matrix_dict,
            "shock_correlation": shock,
            "composition_view": composition,
        }
        self._portfolio_cache[cache_key] = (_time.time(), result)
        return result

    def _check_composition_gaps(
        self,
        weights: list[dict[str, Any]],
        returns_df: pd.DataFrame | None,
        corr_matrix: pd.DataFrame | None,
    ) -> dict[str, Any]:
        """Cross-ticker composition view (pending Row 4 / 04:385).

        Detects concentration, high correlation clusters, and suggests
        missing exposure type. Fail-open: returns status dict, never raises.
        """
        if not weights:
            return {"status": "empty", "gaps": [], "suggestions": []}
        gaps: list[str] = []
        suggestions: list[str] = []
        # Concentration: single weight >40%
        max_w = max((w.get("target_weight", 0) for w in weights), default=0)
        if max_w > 0.4:
            gaps.append(f"concentration {max_w:.0%} in one strategy — single-name risk")
            suggestions.append("consider uncorrelated factor or asset class (mean_reverting / hedged)")
        # Correlation cluster
        if corr_matrix is not None and len(corr_matrix) >= 2:
            # off-diagonal max
            mask = corr_matrix.where(~corr_matrix.isin([1.0])).stack()
            max_corr = float(mask.max()) if not mask.empty else 0.0
            if max_corr > 0.8:
                gaps.append(f"high correlation cluster max {max_corr:.2f} — book moves as one")
                suggestions.append("add low-correlation sleeve (e.g. ranging/mean_reverting when book is trending)")
            elif max_corr > 0.6:
                gaps.append(f"moderate correlation {max_corr:.2f}")
        # Low diversification count
        if len(weights) < 3:
            gaps.append(f"only {len(weights)} active sleeve(s) — under-diversified")
            suggestions.append("add sleeve with complementary regime tag")
        status = "ok" if not gaps else "gaps_detected"
        return {"status": status, "gaps": gaps, "suggestions": suggestions}

    # ------------------------------------------------------------------
    # Daily allocation — regime-aware, outcome-confidence-weighted tilt
    # on top of the base risk-parity weights above (Focus 3 / Step 10).
    # On-demand only by design -- not started from entrypoint.sh, mirroring
    # vinu_research/cli.py::promote_scan_main's precedent that a
    # consequential action (here: allocation-weight changes) stays a
    # command invoked on purpose, not a silent background loop.
    # ------------------------------------------------------------------

    async def _fetch_benchmark_regime(self) -> dict[str, Any]:
        """Current regime read for the configured benchmark symbol.

        Fails open (returns a status dict, never raises) -- this feeds a
        weighting tilt, not a safety gate, so it must never block
        allocation the way OrderGuard's checks correctly block orders.
        """
        return await self._fetch_symbol_regime(self._config.benchmark_symbol)

    async def _fetch_symbol_regime(self, symbol: str) -> dict[str, Any]:
        """Per-symbol regime (19 step2): same classifier as benchmark, run
        on the symbol's own daily closes. Fail-open to unavailable."""
        try:
            resp = await self._http.get(
                f"{self._config.stock_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "adjusted": True},
            )
            if resp.status_code != 200:
                return {"status": "unavailable", "regime": None}
            data = resp.json()
            records = data.get("data") if isinstance(data, dict) else None
            if not records:
                return {"status": "unavailable", "regime": None}
            closes = pd.Series([float(r["close"]) for r in records])
            returns = closes.pct_change().dropna()
            out = classify_current_regime(returns)
            out["symbol"] = symbol
            return out
        except Exception as e:
            LOG.warning("Failed to fetch regime for %s: %s", symbol, e)
            return {"status": "unavailable", "regime": None}

    async def _fetch_outcome_confidence(self, strategy: dict[str, Any]) -> dict[str, Any]:
        """Recent directional accuracy for a strategy, if any is tracked.

        llm_python strategies may have a calibration track record (Phase 7's
        record-outcome path, trade_plan-type artifacts only). Stage 2
        (how-to-make-it-live.md #20): YAML strategies used to have no
        outcome tracking anywhere in this codebase -- always "not_tracked",
        never fabricated, but also never anything else no matter how long
        they ran. See _fetch_yaml_track_record for what they get now.
        """
        if strategy.get("kind") == "yaml":
            return await self._fetch_yaml_track_record(strategy)
        if strategy.get("kind") != "llm_python":
            return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

        artifact_id = strategy.get("artifact_id", "")
        if not artifact_id:
            return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

        n_entries: int
        accuracy: float | None
        try:
            n_entries, accuracy = await self._fetch_calibration_in_process(artifact_id)
        except Exception as e:
            LOG.debug("Failed in-process calibration read for %s, falling back to HTTP: %s", artifact_id, e)
            try:
                resp = await self._http.get(
                    f"{self._config.research_api_url}/research/trade-plan/{artifact_id}/calibration"
                )
                if resp.status_code != 200:
                    return {"source": "unavailable", "accuracy": None, "n_entries": 0}
                data = resp.json()
                n_entries, accuracy = data.get("n_entries", 0), data.get("accuracy")
            except Exception as e2:
                LOG.warning("Failed to fetch outcome confidence for %s: %s", artifact_id, e2)
                return {"source": "unavailable", "accuracy": None, "n_entries": 0}

        if n_entries < self._config.min_calibration_entries_for_tilt:
            return {"source": "insufficient_data", "accuracy": None, "n_entries": n_entries}
        return {"source": "calibration", "accuracy": accuracy, "n_entries": n_entries}

    async def _fetch_yaml_track_record(self, strategy: dict[str, Any]) -> dict[str, Any]:
        """Stage 2 (how-to-make-it-live.md #20): YAML strategies have no
        artifact_id and no discrete open/closed positions the way
        trade_plan strategies do -- there is no `calibration_entries` row
        to read at all, and never will be without inventing a whole new
        position-tracking concept for a portfolio target-weight strategy.

        This derives a directional track record from the two series
        vinu-portfolio already fetches elsewhere for correlation purposes
        (the strategy's own historical target-weight series via
        weights_source, and the symbol's own price history): for each pair
        of consecutive dates where the strategy held a non-flat weight on
        the earlier date, was that weight's sign (long/short) the same
        sign as the symbol's realized return between the two dates? A flat
        (~0) weight is not a directional call and is excluded, not scored
        as wrong.

        Fails open to "not_tracked" (never a fabricated accuracy) if either
        series is unavailable or empty -- same contract the docstring above
        already promised for the "no data" case; the difference now is that
        a strategy that HAS run long enough gets a real answer instead of a
        permanent one.
        """
        symbol = strategy.get("symbol", "")
        weights_source = strategy.get("weights_source", "")
        if not symbol or not weights_source:
            return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

        try:
            w_resp = await self._http.get(weights_source)
            if w_resp.status_code != 200:
                return {"source": "not_tracked", "accuracy": None, "n_entries": 0}
            weights_raw = w_resp.json()
            if not isinstance(weights_raw, list) or not weights_raw:
                return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

            p_resp = await self._http.get(
                f"{self._config.stock_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "adjusted": True},
            )
            if p_resp.status_code != 200:
                return {"source": "not_tracked", "accuracy": None, "n_entries": 0}
            candles = (p_resp.json() or {}).get("data") or []
            if not candles:
                return {"source": "not_tracked", "accuracy": None, "n_entries": 0}
        except Exception as e:
            LOG.warning(
                "Failed to fetch YAML track record inputs for %s: %s", strategy.get("name", ""), e,
            )
            return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

        weight_by_date: dict[str, float] = {}
        for w in weights_raw:
            d = w.get("date")
            if d is None:
                continue
            weight_by_date[str(d)[:10]] = float(w.get("weight", 0.0) or 0.0)

        close_by_date: dict[str, float] = {}
        for c in candles:
            bar_ts = c.get("bar_ts")
            if bar_ts is None or c.get("close") is None:
                continue
            date_str = datetime.fromtimestamp(int(bar_ts), tz=timezone.utc).date().isoformat()
            close_by_date[date_str] = float(c["close"])

        dates = sorted(set(weight_by_date) & set(close_by_date))
        correct = 0
        total_calls = 0
        for prev_date, cur_date in zip(dates, dates[1:]):
            prev_weight = weight_by_date.get(prev_date)
            prev_close = close_by_date.get(prev_date)
            cur_close = close_by_date.get(cur_date)
            if prev_weight is None or not prev_close or cur_close is None:
                continue
            if abs(prev_weight) < 1e-9:
                continue  # flat -- no directional call made, not a wrong prediction
            realized_return = (cur_close - prev_close) / prev_close
            if realized_return == 0:
                continue
            total_calls += 1
            if (prev_weight > 0) == (realized_return > 0):
                correct += 1

        if total_calls == 0:
            return {"source": "not_tracked", "accuracy": None, "n_entries": 0}
        if total_calls < self._config.min_calibration_entries_for_tilt:
            return {"source": "insufficient_data", "accuracy": None, "n_entries": total_calls}
        return {
            "source": "yaml_track_record",
            "accuracy": correct / total_calls,
            "n_entries": total_calls,
        }

    async def _fetch_calibration_in_process(self, artifact_id: str) -> tuple[int, float]:
        from vinu_portfolio.research_link import get_strategy_store
        from vinu_research.forecast_skill import compute_calibration

        store = get_strategy_store()
        entries = await asyncio.to_thread(store.get_calibration_entries, artifact_id)
        result = compute_calibration(entries)
        return result.n_entries, result.accuracy

    def _load_tags(self) -> dict[str, Any]:
        """Load strategy-tags/tags.yaml once and cache it on the instance.

        This is a dev-time knowledge-library file, not guaranteed to be
        present in every deployment (the default path resolves to a host
        location outside this container's build context, so it's already
        absent in the running Docker deployment today) -- missing/
        unreadable is treated as "no tags known", not a fatal error,
        consistent with this whole pipeline's fail-open-on-tilt-data
        convention.
        """
        if self._tags_cache is not None:
            return self._tags_cache
        try:
            with open(self._config.tags_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            self._tags_cache = loaded.get("strategies", {})
        except OSError as e:
            LOG.warning("Could not load strategy tags from %s: %s", self._config.tags_path, e)
            self._tags_cache = {}
        return self._tags_cache

    def _regime_alignment_multiplier(self, strategy_name: str, regime: str | None) -> float:
        tags = self._load_tags()
        entry = tags.get(strategy_name)
        if entry is None or regime is None:
            return 1.0
        wanted_tags = _REGIME_TO_TAGS.get(regime)
        if not wanted_tags:
            return 1.0  # high_vol / unmapped regime -- no directional tag dimension to compare
        strategy_regimes = set(entry.get("regime", []))
        bound = self._config.regime_tilt_bound
        return 1.0 + bound if strategy_regimes & wanted_tags else 1.0 - bound

    def _outcome_confidence_multiplier(self, confidence: dict[str, Any]) -> float:
        accuracy = confidence.get("accuracy")
        if accuracy is None:
            return 1.0  # untracked/insufficient data keeps the base weight, not penalized
        bound = self._config.outcome_tilt_bound
        return 1.0 + bound * (2.0 * accuracy - 1.0)

    def _confidence_gradient_multiplier(self, strategy: dict[str, Any]) -> float:
        """Stage 2 (how-to-make-it-live.md #34): promotion.meets_promotion_bar()
        is a binary pass/fail gate -- a strategy at deflated Sharpe 0.951
        (bare pass) and one at 0.99 (comfortable pass) cleared the exact
        same threshold and, before this, received identical downstream
        allocation weight. deflated_sharpe is itself a probability bounded
        to [0, 1] (see walk_forward.deflated_sharpe_ratio's own docstring --
        despite the name it is not a Sharpe ratio), so the meaningful range
        to spread across is [promotion_deflated_sharpe_threshold, 1.0], not
        an unbounded scale.

        Only applies to llm_python strategies -- YAML strategies never go
        through this promotion bar at all, so there is no margin to read.
        Same +-bound linear-map shape as _outcome_confidence_multiplier
        above, at the low end (bare-minimum pass) rather than the middle
        (accuracy 0.5) since a below-threshold deflated_sharpe should
        never reach here under normal operation -- the promotion gate
        already rejected it -- and a force=true override should size as
        conservatively as a bare pass, not be treated as neutral.
        """
        if strategy.get("kind") != "llm_python":
            return 1.0
        deflated_sharpe = strategy.get("deflated_sharpe")
        if deflated_sharpe is None:
            return 1.0
        threshold = self._config.promotion_deflated_sharpe_threshold
        span = 1.0 - threshold
        if span <= 0:
            return 1.0
        frac = (float(deflated_sharpe) - threshold) / span
        frac = max(0.0, min(1.0, frac))
        bound = self._config.confidence_tilt_bound
        return (1.0 - bound) + frac * (2.0 * bound)

    @staticmethod
    def _detect_symbol_conflicts(weights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """item #23 finding #1: **decided policy is net**, not an open
        question. A single brokerage account cannot literally hold two
        opposing positions in the same symbol at once ("keep separate"
        isn't realizable without sub-accounts, out of scope); "block"
        would leave a stale/unmanaged position sitting whenever two
        strategies disagree, which is worse than converging on their
        actual net conviction. Netting is already enforced correctly,
        exactly once, at the one correct point -- `vinu-live`'s
        `SignalTranslator._net_by_symbol` (item #24 finding #2), right
        before an order is built. It is deliberately NOT re-implemented
        here: `compute_daily_allocation`'s entire pipeline (deflated-Sharpe
        confidence-gradient tilt, outcome-confidence tracking by
        artifact_id, sleeve/interval bucketing) is keyed by STRATEGY
        identity throughout, so collapsing two strategies' rows into one
        this early would silently orphan or corrupt all of that
        bookkeeping -- a second, redundant enforcement point that could
        only ever duplicate `vinu-live`'s math, never improve on it.

        What this function is for is visibility at the conflict's
        SOURCE, now including a severity measure so a conflict that's
        mostly overlap (e.g. 0.05 vs 0.04, same direction) doesn't read
        the same as strategies actively fighting (e.g. +0.21 vs -0.19):
        `gross_weight` (sum of |contribution|), `net_weight` (what
        actually survives netting), and `severity` = 1 - |net|/gross when
        gross > 0 (0.0 = no cancellation at all, up to 1.0 = fully
        canceled out). Severe, opposite-direction conflicts are escalated
        to a real alert by `_notify_severe_symbol_conflicts` (called from
        `compute_daily_allocation`, since that needs the async HTTP
        client this staticmethod deliberately doesn't have) -- the same
        "don't leave it as a WARNING log nobody's tailing" gap item #23
        finding #4 already closed for agent-API-unreachable, applied here
        to a second real risk-visibility gap.
        """
        by_symbol: dict[str, list[dict[str, Any]]] = {}
        for w in weights:
            symbol = (w.get("symbol") or "").upper()
            if not symbol:
                continue
            by_symbol.setdefault(symbol, []).append(w)

        conflicts: list[dict[str, Any]] = []
        for symbol, entries in by_symbol.items():
            if len(entries) < 2:
                continue
            contributions = [
                {"strategy_name": e.get("name", ""), "target_weight": e.get("target_weight", 0.0)}
                for e in entries
            ]
            net_weight = round(sum(c["target_weight"] for c in contributions), 4)
            gross_weight = round(sum(abs(c["target_weight"]) for c in contributions), 4)
            severity = round(1.0 - abs(net_weight) / gross_weight, 4) if gross_weight > 0 else 0.0
            signs = {1 if c["target_weight"] >= 0 else -1 for c in contributions}
            opposite_direction = len(signs) > 1
            if opposite_direction:
                LOG.warning(
                    "Symbol conflict: %s targeted by %d strategies in opposite "
                    "directions: %s (net %.4f of gross %.4f, %.0f%% canceled) -- "
                    "netted automatically before execution (policy: net, decided "
                    "-- see vinu-live's SignalTranslator._net_by_symbol)",
                    symbol, len(entries), contributions, net_weight, gross_weight, severity * 100,
                )
            conflicts.append({
                "symbol": symbol,
                "contributions": contributions,
                "net_weight": net_weight,
                "gross_weight": gross_weight,
                "severity": severity,
                "opposite_direction": opposite_direction,
            })
        return conflicts

    # item #23 finding #1: guessed starting constants for "severe enough to
    # alert a human," same posture as FORWARD_HORIZON_BARS/floor_multiple
    # elsewhere in this file -- meant to be revisited once real data exists
    # on how often/how large these conflicts actually run.
    _SEVERE_CONFLICT_SEVERITY = 0.5
    _SEVERE_CONFLICT_GROSS_WEIGHT = 0.05

    async def _notify_severe_symbol_conflicts(self, conflicts: list[dict[str, Any]]) -> None:
        """Best-effort escalation for the conflicts worth a human's
        attention -- opposite-direction, at least half canceled out, and
        big enough in gross size to matter. Never raises: a notification
        failure must never be treated as a failure of the allocation
        computation it's reporting on, same posture `_halt_trading` and
        every /notify/* route already establish."""
        for c in conflicts:
            if not c.get("opposite_direction"):
                continue
            if c.get("severity", 0.0) < self._SEVERE_CONFLICT_SEVERITY:
                continue
            if c.get("gross_weight", 0.0) < self._SEVERE_CONFLICT_GROSS_WEIGHT:
                continue
            try:
                await self._http.post(
                    f"{self._config.agent_api_url}/agent/notify/symbol-conflict",
                    json={
                        "symbol": c["symbol"],
                        "contributions": c["contributions"],
                        "net_weight": c["net_weight"],
                        "gross_weight": c["gross_weight"],
                        "severity": c["severity"],
                    },
                )
            except Exception as e:
                LOG.warning(
                    "Failed to escalate severe symbol conflict for %s via %s: %s",
                    c.get("symbol"), self._config.agent_api_url, e,
                )

    @staticmethod
    def _drawdown_action_multiplier(action: str) -> float:
        """item #23 finding #2's own fix mechanism: the circuit breaker's
        action ladder is ok -> halve -> flat -> halt. `halve` deploys half
        the usual capital, `flat`/`halt` deploy none -- applied to
        `deployable_equity` (the sizing step), not `target_weight` (a
        relative allocation that always renormalizes to 1.0, where a
        uniform multiplier would be a no-op -- see compute_daily_
        allocation's own comment at the call site). `halt` already blocks
        order submission entirely via the real kill switch _halt_trading
        engages, so zeroing deployable_equity here too is belt-and-
        suspenders, not the primary enforcement. Unknown/malformed action
        strings fail open to 1.0, same posture as every other tilt input
        in this pipeline (_load_tags's docstring)."""
        return {"ok": 1.0, "halve": 0.5, "flat": 0.0, "halt": 0.0}.get(action, 1.0)

    async def _maturity_capital_multiplier(self) -> float:
        """item #4 (system-wide-audit-and-design, "gradual capital
        scaling"): a system-wide MaturityAssessment (cold_start/
        paper_only/early_live/mature) previously only ever reached an
        LLM prompt (vinu-research's own trade_plan_authoring.py), never
        capital sizing. Applied to `deployable_equity` -- the same
        whole-portfolio scale-down mechanism `_drawdown_action_multiplier`
        above already uses -- because this is one system-wide value
        (computed across every strategy's own trade/paper history), not
        a per-strategy signal the per-strategy tilt loop could vary.

        No-op (1.0) when the feature is disabled (default) or the
        in-process assessment call fails for any reason -- see this
        service's own config field docstring for why this fails open
        rather than conservatively restricting on a missing signal.
        """
        if not self._config.maturity_capital_gating_enabled:
            return 1.0
        try:
            from vinu_portfolio.research_link import get_maturity_assessment
            assessment = await asyncio.to_thread(get_maturity_assessment)
        except Exception as e:
            LOG.warning("Maturity assessment unavailable, deploying at full capital: %s", e)
            _record_edge("maturity.status->portfolio.capital", "missing", str(e))
            return 1.0
        _record_edge("maturity.status->portfolio.capital", "received", f"tier={assessment.tier}")

        from vinu_research.maturity_assessor import (
            TIER_COLD_START, TIER_EARLY_LIVE, TIER_MATURE, TIER_PAPER_ONLY,
        )
        return {
            TIER_COLD_START: self._config.maturity_capital_multiplier_cold_start,
            TIER_PAPER_ONLY: self._config.maturity_capital_multiplier_paper_only,
            TIER_EARLY_LIVE: self._config.maturity_capital_multiplier_early_live,
            TIER_MATURE: 1.0,
        }.get(assessment.tier, 1.0)

    # item #23 finding #5: a candidate whose tilted weight rounds to
    # (effectively) zero never gets any capital -- "not funded," the same
    # concept as a screener symbol failing a hard filter, just continuous
    # (multiplicative tilts) rather than binary (a threshold check).
    _NOT_FUNDED_WEIGHT_THRESHOLD = 0.0001

    @staticmethod
    def _detect_not_funded(tilted: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """item #23 finding #5: `allocation_history.py` persisted what was
        allocated, never why a candidate wasn't funded -- a smaller
        instance of the same recurring pattern items #3/#16.2/#18.3/#21.3
        already named, closed the same way with the shared `RejectionRecord`
        shape (`vinu_infra.rejection_log`) rather than inventing a new
        format for the fourth time.

        Unlike a screener hard filter, nothing in this pipeline makes a
        binary accept/reject call -- every strategy gets SOME weight, just
        possibly one that rounds to zero after four independently-computed
        multiplicative tilts (regime/outcome/confidence-gradient/risk-
        budget) and renormalization. So "why" here is necessarily a
        heuristic over already-computed, already-visible numbers (the
        smallest of the four multipliers, or the concentration cap if none
        of them explain it), not a definitive single cause the way a
        `hard_filter_reasons()` bound violation is -- documented as such
        in `rejection_category`/`rejection_detail`, not overclaimed."""
        from vinu_infra.rejection_log import record_rejection

        records: list[dict[str, Any]] = []
        for t in tilted:
            if t.get("target_weight", 0.0) > PortfolioService._NOT_FUNDED_WEIGHT_THRESHOLD:
                continue
            factors = {
                "regime_alignment": t.get("regime_multiplier", 1.0),
                "outcome_confidence": t.get("outcome_multiplier", 1.0),
                "confidence_gradient": t.get("confidence_gradient_multiplier", 1.0),
                "risk_budget": t.get("risk_budget_multiplier", 1.0),
            }
            smallest_name, smallest_value = min(factors.items(), key=lambda kv: kv[1])
            if smallest_value < 1.0:
                category = smallest_name
                detail = (
                    f"smallest tilt was {smallest_name}={smallest_value:.4f} "
                    f"(base_weight={t.get('base_weight', 0.0):.4f}, all tilts: {factors})"
                )
            else:
                # every tilt was neutral (>=1.0) -- the zero came from
                # cap_concentration's redistribution or simply a large
                # strategy count diluting an equal/inverse-vol starting
                # weight below the rounding threshold, not any one tilt.
                category = "concentration_or_dilution"
                detail = (
                    f"no tilt reduced this candidate (all >= 1.0: {factors}) -- "
                    f"base_weight={t.get('base_weight', 0.0):.4f} before concentration capping/normalization"
                )
            records.append(
                record_rejection(
                    "portfolio_strategy", t.get("name", ""), "daily_allocation",
                    category, detail,
                ).to_dict()
            )
        return records

    def allocation_history_summaries(self, limit: int = 30) -> list[dict[str, Any]]:
        """Newest-first one-line summaries of every persisted daily allocation. The store
        had readers but no HTTP route anywhere, so what was allocated (and what was left
        unfunded) on past days could not be read without the database file."""
        rows = self._allocation_history.list_allocations()[: max(0, limit)]
        _record_edge("portfolio.not_funded_history->portfolio.api", "received" if rows else "empty", f"{len(rows)} allocation(s) read")
        return [
            {
                "allocation_date": a.allocation_date, "created_at": a.created_at,
                "n_weights": len(a.weights), "n_not_funded": len(a.not_funded),
                "account_equity": a.account_equity, "deployable_equity": a.deployable_equity,
            }
            for a in rows
        ]

    def latest_not_funded(self) -> dict[str, Any] | None:
        """The most recent persisted allocation's unfunded candidates, each a
        `RejectionRecord` dict with its heuristic reason (smallest tilt, or concentration /
        dilution). None when no allocation has ever been recorded -- distinct from an empty
        `not_funded` list (an allocation ran and everything was funded)."""
        rows = self._allocation_history.list_allocations()
        _record_edge("portfolio.not_funded_history->portfolio.api", "received" if rows else "empty", f"{len(rows)} allocation(s) on record")
        if not rows:
            return None
        latest = rows[0]
        return {
            "allocation_date": latest.allocation_date, "created_at": latest.created_at,
            "count": len(latest.not_funded), "not_funded": latest.not_funded,
        }

    async def compute_daily_allocation(
        self, extra_candidates: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Regime-aware, outcome-confidence-weighted allocation on top of
        the base risk-parity weights from build_portfolio().

        This is a defensible v1, not a solved probability model: two
        bounded multiplicative tilts (regime alignment, outcome confidence)
        applied to the existing risk-parity base and renormalized. See
        vinu-agent/skills/daily-allocation/SKILL.md for the full reasoning
        and known limitations (regime-vocabulary mapping, YAML-strategy
        outcome blind spot, the still-open ShadowEvaluator gap this only
        partially compensates for).

        `extra_candidates`: same PEND-batch pass-through as build_portfolio().
        """
        base = await self.build_portfolio(extra_candidates=extra_candidates)
        if base["status"] != "ok":
            return base

        import os as _os

        regime_info = await self._fetch_benchmark_regime()
        regime = regime_info.get("regime")
        # Per-symbol regime (19 step2): when enabled, each sleeve's own
        # symbol regime overrides benchmark for its tilt. Default off keeps
        # benchmark-only behavior. Fail-open: unavailable -> benchmark.
        _per_sym = _os.environ.get("VINU_PORTFOLIO_PER_SYMBOL_REGIME", "false").lower() in ("1", "true", "yes")
        per_symbol_regime: dict[str, Any] = {}
        if _per_sym:
            _syms = sorted({(w.get("symbol") or w.get("name", "")).upper() for w in base["weights"] if w.get("symbol") or w.get("name")})
            for _s in _syms[:10]:
                per_symbol_regime[_s] = await self._fetch_symbol_regime(_s)

        # item #23 finding #3: one more real, already-computed risk signal
        # folded in as the same kind of bounded multiplicative tilt as
        # regime/outcome/confidence-gradient above -- per-symbol, so
        # unlike the drawdown ladder below it genuinely changes each
        # symbol's weight *relative to the others* (redistributes away
        # from a troubled position), which survives the renormalize-to-
        # 1.0 step further down instead of being cancelled by it. Equity
        # is fetched here (moved up from later in this method, a pure
        # reordering -- nothing between here and its old call site reads
        # it) since risk_budget's per-symbol tiers need current broker
        # positions/equity, and there's no point fetching positions at
        # all when there's no equity to size against.
        equity = await self._fetch_account_equity()
        positions = await self._fetch_positions() if equity is not None else []
        risk_budget = compute_risk_budget(positions, equity, regime=regime, tracker=self._risk_tracker)
        risk_mult_by_symbol = {
            str(s.get("symbol", "")).upper(): s.get("suggested_size_multiplier", 1.0)
            for s in risk_budget.symbols
        }
        # item #23 finding #2: the drawdown ladder's halve/flat/halt is
        # deliberately NOT applied here alongside the tilt above --
        # target_weight is a *relative* allocation (always renormalized to
        # sum to 1.0), so a uniform multiplier applied to every weight
        # before that renormalization is a mathematical no-op (scale
        # everything by 0.5, renormalize back to 1.0, unchanged). "Halve
        # size"/"exit to flat" means reduce *total deployed capital*, which
        # is `deployable_equity` below, not the weight fractions -- same
        # place `reserve_fraction` already applies its own scale-down for
        # exactly this reason (visible in the response, never folded into
        # target_weight/base_weight).
        drawdown_status = self._drawdown_status_store.get()
        # An empty `updated_at` means the drawdown monitor has never written a status: the ladder is then running on
        # its default ("ok") and silently doing nothing -- exactly the not-running case worth surfacing.
        _record_edge(
            "drawdown_status->portfolio.allocation", "received" if drawdown_status.updated_at else "empty",
            f"action={drawdown_status.action}" if drawdown_status.updated_at else "the drawdown monitor has never recorded a status",
        )
        drawdown_mult = self._drawdown_action_multiplier(drawdown_status.action)
        maturity_mult = await self._maturity_capital_multiplier()

        by_name = {s["name"]: s for s in base["strategies"]}
        tilted: list[dict[str, Any]] = []
        for w in base["weights"]:
            strategy = by_name.get(w["name"], {})
            confidence = await self._fetch_outcome_confidence(strategy)
            _sym = (w.get("symbol") or "").upper()
            _local = (per_symbol_regime.get(_sym) or {}).get("regime") if _sym else None
            regime_mult = self._regime_alignment_multiplier(w["name"], _local or regime)
            outcome_mult = self._outcome_confidence_multiplier(confidence)
            confidence_gradient_mult = self._confidence_gradient_multiplier(strategy)
            # Not applied for a symbol risk_budget has no position for
            # (nothing held yet -> no P&L-based signal to tilt on, stays
            # neutral at 1.0) -- same "no signal is not evidence of harm"
            # posture the rest of this pipeline already uses.
            risk_mult = risk_mult_by_symbol.get(_sym, 1.0) if _sym else 1.0
            tilted.append({
                **w,
                "base_weight": w["target_weight"],
                "regime_multiplier": round(regime_mult, 4),
                "outcome_multiplier": round(outcome_mult, 4),
                "confidence_gradient_multiplier": round(confidence_gradient_mult, 4),
                "risk_budget_multiplier": round(risk_mult, 4),
                "outcome_source": confidence.get("source"),
                "target_weight": (
                    w["target_weight"] * regime_mult * outcome_mult
                    * confidence_gradient_mult * risk_mult
                ),
            })

        total = sum(t["target_weight"] for t in tilted)
        if total > 0:
            for t in tilted:
                t["target_weight"] = round(t["target_weight"] / total, 4)

        # Hysteresis 2d no flip-flop (19 step3): changes smaller than
        # VINU_PORTFOLIO_MIN_WEIGHT_CHANGE (default 0.02) hold old weight.
        # Renormalize after. First run (no memory) passes through.
        try:
            _min_chg = float(_os.environ.get("VINU_PORTFOLIO_MIN_WEIGHT_CHANGE", "0.02"))
        except ValueError:
            _min_chg = 0.02
        if self._last_weights and _min_chg > 0:
            for t in tilted:
                _old_w = self._last_weights.get(t["name"])
                if _old_w is not None and abs(t["target_weight"] - _old_w) < _min_chg:
                    t["target_weight"] = _old_w
            _tot2 = sum(t["target_weight"] for t in tilted)
            if _tot2 > 0:
                for t in tilted:
                    t["target_weight"] = round(t["target_weight"] / _tot2, 4)
        # Composition action cap 20% (13 step1): no single sleeve moves more
        # than VINU_PORTFOLIO_MAX_ACTION per cycle -- big rotations phase in
        # gradually. New sleeves (no memory) uncapped first run. Renormalize.
        try:
            _max_act = float(_os.environ.get("VINU_PORTFOLIO_MAX_ACTION", "0.20"))
        except ValueError:
            _max_act = 0.20
        if self._last_weights and _max_act > 0:
            for t in tilted:
                _old_w = self._last_weights.get(t["name"])
                if _old_w is not None:
                    _d = t["target_weight"] - _old_w
                    if abs(_d) > _max_act:
                        t["target_weight"] = round(_old_w + _max_act * (1 if _d > 0 else -1), 4)
            _tot3 = sum(t["target_weight"] for t in tilted)
            if _tot3 > 0:
                for t in tilted:
                    t["target_weight"] = round(t["target_weight"] / _tot3, 4)

        # Re-enforce max_per_strategy_weight: build_portfolio's base weights
        # already passed cap_concentration once (line ~325), but the three
        # multiplicative tilts above (regime/outcome/confidence-gradient,
        # each up to 1.3x uncapped) plus hysteresis/action-cap renormalize
        # can push an already-capped sleeve back over the limit -- the same
        # bug cap_concentration's own docstring documents fixing for
        # build_portfolio, reintroduced here by the tilt pipeline having no
        # idea the cap exists. Same iterative cap+redistribute, not a plain
        # min(w, cap)+renormalize (which would just reintroduce it again).
        _tilt_weights = {t["name"]: t["target_weight"] for t in tilted}
        _capped = cap_concentration(_tilt_weights, self._config.max_per_strategy_weight)
        for t in tilted:
            t["target_weight"] = round(_capped.get(t["name"], t["target_weight"]), 4)

        self._last_weights = {t["name"]: t["target_weight"] for t in tilted}

        # Reserve fund (restart/safety capital ordinary sizing can't touch):
        # apply_position_sizing sizes against deployable_equity, never raw
        # equity, once reserve_fraction is configured. Default 0.0 makes
        # deployable_equity == equity, a no-op. account_equity in the
        # response below stays the real total either way -- the reserve is
        # visible, not silently subtracted.
        #
        # item #23 finding #2: the drawdown ladder's action multiplier
        # applies here too, same reasoning -- "halve" deploys half the
        # capital (drawdown_mult=0.5), "flat"/"halt" deploy none (0.0),
        # "ok" is a no-op (1.0). Stacks with the reserve fraction above
        # rather than replacing it -- both are real, independent reasons
        # to hold capital back. item #4: the maturity capital multiplier
        # stacks here too, same reasoning -- a still-unproven strategy
        # population deploys a fraction of capital regardless of how
        # good any individual signal looks today, exactly the "start
        # small, scale up as track record grows" ask.
        deployable_equity = (
            equity * (1.0 - self._config.reserve_fraction) * drawdown_mult * maturity_mult
            if equity is not None else None
        )
        if deployable_equity is not None:
            tilted = apply_position_sizing(tilted, deployable_equity, target_vol=self._config.target_volatility)

        # Sleeves (19 step3): subtotal weights by style tag AND by interval.
        # Interval source: Artifact.timeframe (vinu-research/vinu_research/
        # models.py), read via `by_name` (already built above from
        # base["strategies"]) -- replaces a regex-on-strategy-name guess
        # (-1d-/-1H-/-15min-) that stood in for this before the field
        # existed. Unknown/missing -> "daily", same fallback as before.
        tags = self._load_tags()
        sleeves: dict[str, float] = {}
        interval_sleeves: dict[str, float] = {}
        for t in tilted:
            _style = str((tags.get(t["name"]) or {}).get("style", "untagged"))
            sleeves[_style] = round(sleeves.get(_style, 0.0) + t["target_weight"], 4)
            _iv = str(by_name.get(t["name"], {}).get("timeframe") or "daily")
            interval_sleeves[_iv] = round(interval_sleeves.get(_iv, 0.0) + t["target_weight"], 4)

        reserve_amount = (
            round(equity * self._config.reserve_fraction, 2) if equity is not None else None
        )
        deployable_equity_rounded = (
            round(deployable_equity, 2) if deployable_equity is not None else None
        )
        # item #23 finding #1: decided policy is net (see
        # _detect_symbol_conflicts's own docstring) -- this is visibility
        # at the source plus escalation for the severe cases, not a second
        # enforcement point.
        symbol_conflicts = self._detect_symbol_conflicts(tilted)
        await self._notify_severe_symbol_conflicts(symbol_conflicts)
        # item #23 finding #5: same "visible, not just silently folded"
        # treatment as symbol_conflicts above -- a candidate that ends up
        # unfunded is otherwise indistinguishable from one that was never
        # evaluated at all.
        not_funded = self._detect_not_funded(tilted)
        result = {
            **base,
            "weights": tilted,
            "regime": regime_info,
            "per_symbol_regime": per_symbol_regime,
            "sleeves": sleeves,
            "interval_sleeves": interval_sleeves,
            "symbol_conflicts": symbol_conflicts,
            "not_funded": not_funded,
            "account_equity": equity,
            "reserve_fraction": self._config.reserve_fraction,
            "reserve_amount": reserve_amount,
            "deployable_equity": deployable_equity_rounded,
            # item #23 findings #2/#3: visible, not just silently folded
            # into target_weight -- a caller can see *why* sizing was cut,
            # same transparency regime_multiplier/outcome_multiplier
            # already give for the other two tilts.
            "drawdown_status": {
                "action": drawdown_status.action,
                "current_drawdown": drawdown_status.current_drawdown,
                "threshold_breached": drawdown_status.threshold_breached,
            },
            "risk_budget": risk_budget.to_dict(),
            # item #4: same "visible, not silently folded" transparency
            # as reserve_fraction/drawdown above -- always present (1.0
            # when the feature is disabled, the same value drawdown's own
            # "ok" no-op reports) rather than only appearing once enabled.
            "maturity_capital_multiplier": round(maturity_mult, 4),
        }

        # Dated history (19 foundation-fixes follow-up): nothing calls this
        # method on a guaranteed once-daily cadence, so the store's own
        # same-day upsert is what makes recording on every call safe. Never
        # allowed to break the response itself -- best-effort, same posture
        # as every other audit writer in this codebase.
        try:
            self._allocation_history.record_daily_allocation(
                weights=tilted, sleeves=sleeves, interval_sleeves=interval_sleeves,
                account_equity=equity, reserve_fraction=self._config.reserve_fraction,
                reserve_amount=reserve_amount, deployable_equity=deployable_equity_rounded,
                not_funded=not_funded,
            )
        except Exception as exc:  # noqa: BLE001 -- best-effort, never blocks the response
            LOG.warning("Allocation history write failed: %s", exc)

        if self._config.shared_root:
            for t in tilted:
                sym = (t.get("symbol") or t.get("name", "")).upper()
                if not sym:
                    continue
                write_ticker_profile_key(
                    self._config.shared_root, sym, "vinu_portfolio",
                    {
                        "target_weight": t["target_weight"],
                        "base_weight": t.get("base_weight"),
                        "regime_multiplier": t.get("regime_multiplier"),
                        "outcome_multiplier": t.get("outcome_multiplier"),
                    },
                )

        return result

    async def compute_daily_game_plan(
        self, allocation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """`allocation`: lets a caller that already has a fresh
        `compute_daily_allocation()` result (e.g. `compute_risk_status`)
        pass it straight through instead of this method fetching its own
        -- see `compute_risk_status`'s own docstring for the redundant-
        recompute this closes. `None` (every other/existing caller)
        preserves the original behavior exactly: fetch it here."""
        if allocation is None:
            allocation = await self.compute_daily_allocation()
        if allocation.get("status") != "ok":
            return allocation

        regime_info = allocation.get("regime", {})
        equity = allocation.get("account_equity")
        base = allocation  # already includes build_portfolio output

        by_name = {s["name"]: s for s in base["strategies"]}
        symbols: list[SymbolPlan] = []
        n_available = 0
        n_total = len(allocation["weights"])

        for w in allocation["weights"]:
            strategy = by_name.get(w["name"], {})
            plan_data, plan_found = await self._fetch_trade_plan(strategy)
            forecast = None
            invalidation_conditions = None
            p_failure = None
            if plan_data:
                forecast = plan_data.get("forecast")
                invalidation_conditions = plan_data.get("invalidation_conditions")
                p_failure = plan_data.get("p_failure")

            outcome_source = w.get("outcome_source", "not_tracked")

            plan = SymbolPlan(
                ticker=w.get("symbol", ""),
                target_weight=w.get("target_weight", 0.0),
                base_weight=w.get("base_weight", 0.0),
                regime_multiplier=w.get("regime_multiplier", 1.0),
                outcome_multiplier=w.get("outcome_multiplier", 1.0),
                confidence_gradient_multiplier=w.get("confidence_gradient_multiplier", 1.0),
                outcome_source=outcome_source,
                position_size=w.get("position_size"),
                direction=w.get("direction"),
                forecast=forecast,
                invalidation_conditions=invalidation_conditions,
                p_failure=p_failure,
                shock_correlation=None,
                plan_status="found" if plan_found else "no_plan",
            )
            symbols.append(plan)
            if plan_found:
                n_available += 1

        regime_available = bool(regime_info) and regime_info.get("regime") is not None
        equity_available = equity is not None

        n_data_points = n_total + 2  # + regime + equity, each counted once per plan
        n_available_points = n_available + int(regime_available) + int(equity_available)
        readiness_score = n_available_points / max(n_data_points, 1)
        ready = readiness_score >= self._config.game_plan_readiness_threshold
        readiness_flags = {
            "n_total": n_total,
            "n_with_plan": n_available,
            "regime_available": regime_available,
            "equity_available": equity_available,
            "readiness_score": round(readiness_score, 4),
            "game_ready": ready,
        }

        game_plan = DailyGamePlan(
            date=base.get("timestamp", datetime.now(timezone.utc).isoformat()),
            readiness_score=round(readiness_score, 4),
            readiness_flags=readiness_flags,
            n_symbols=n_total,
            symbols=[s.to_dict() for s in symbols],
            portfolio={
                "n_strategies": base.get("n_strategies", 0),
                "status": base.get("status"),
                "strategy_names": [s["name"] for s in base.get("strategies", [])],
            },
            regime=regime_info,
            shock_correlation=base.get("shock_correlation"),
            account_equity=equity,
        )
        return game_plan.to_dict()

    async def _fetch_trade_plan(
        self, strategy: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, bool]:
        if strategy.get("kind") != "llm_python":
            return None, False
        artifact_id = strategy.get("artifact_id", "")
        if not artifact_id:
            return None, False

        try:
            data = await self._fetch_trade_plan_in_process(artifact_id)
            if data is None:
                return None, False
            return data, True
        except Exception as e:
            LOG.debug("Failed in-process trade-plan read for %s, falling back to HTTP: %s", artifact_id, e)

        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/trade-plan/{artifact_id}"
            )
            if resp.status_code != 200:
                return None, False
            data = resp.json()
            return data, True
        except Exception as e:
            LOG.warning("Failed to fetch trade plan for %s: %s", artifact_id, e)
            return None, False

    async def _fetch_trade_plan_in_process(self, artifact_id: str) -> dict[str, Any] | None:
        from vinu_portfolio.research_link import get_strategy_store

        store = get_strategy_store()
        artifact = await asyncio.to_thread(store.get_artifact, artifact_id)
        if artifact is None or artifact.type != "trade_plan":
            return None
        return {
            "artifact_id": artifact.artifact_id,
            "type": artifact.type,
            "name": artifact.name,
            "universe": artifact.universe,
            "status": artifact.status.value,
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
            "trade_plan_data": artifact.trade_plan_data,
        }

    async def _fetch_account_equity(self) -> float | None:
        """Live equity, reused from the same source drawdown_scheduler.py already polls."""
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data.get("configured"):
                return None
            equity = data.get("equity")
            return float(equity) if equity is not None else None
        except Exception as e:
            LOG.warning("Failed to fetch account equity: %s", e)
            return None

    async def _fetch_positions(self) -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
            if resp.status_code != 200:
                return []
            return resp.json()
        except Exception as e:
            LOG.warning("Failed to fetch positions: %s", e)
            return []

    async def compute_risk_status(self) -> dict[str, Any]:
        """Known redundancy this used to have, now closed: this method's
        own call chain used to be compute_daily_game_plan() ->
        compute_daily_allocation() (which, since item #23 findings #2/#3's
        fix, ALSO fetches positions and computes a risk_budget internally
        for its own risk_budget_multiplier tilt) -- then this method
        fetched positions and computed risk_budget a SECOND time from
        scratch. Not a correctness bug (DailyPositionTracker.record_
        unrealized_pnl's own "worst reading, immune to repeated identical
        reads" design made it idempotent), but a real duplicate fetch/
        compute, same class of problem this file's own _portfolio_cache
        was already built to solve for build_portfolio(). Fixed by
        computing the allocation once here and threading it through
        compute_daily_game_plan (which otherwise still fetches its own),
        reusing its already-computed risk_budget/regime directly.
        """
        allocation = await self.compute_daily_allocation()
        if allocation.get("status") != "ok":
            return allocation

        game_plan = await self.compute_daily_game_plan(allocation=allocation)

        regime = None
        if allocation.get("regime"):
            regime = allocation["regime"].get("regime")

        result = dict(allocation.get("risk_budget") or {})
        result["regime"] = regime
        result["game_plan_readiness"] = game_plan.get("readiness_score")
        return result
