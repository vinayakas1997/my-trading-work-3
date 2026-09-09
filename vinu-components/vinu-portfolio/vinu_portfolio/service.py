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

from vinu_portfolio.config import PortfolioConfig, load_config
from vinu_portfolio.game_plan import DailyGamePlan, SymbolPlan
from vinu_portfolio.regime import classify_current_regime
from vinu_portfolio.risk_budget import compute_risk_budget, DailyPositionTracker
from vinu_portfolio.shock_correlation import dcc_shock_correlation
from vinu_portfolio.sizing import apply_position_sizing

LOG = logging.getLogger(__name__)

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
        # Hysteresis (19 step3): last tilted weights, no flip-flop on noise.
        self._last_weights: dict[str, float] = {}

    async def close(self) -> None:
        await self._http.aclose()

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
            }
            for a in data
        ]

    async def _list_llm_strategies_in_process(self) -> list[dict[str, Any]]:
        from vinu_portfolio.research_link import get_strategy_store
        from vinu_research.models import ArtifactStatus

        store = get_strategy_store()
        artifacts = await asyncio.to_thread(store.list_artifacts_by_statuses, [ArtifactStatus.ACTIVE])
        return [
            {"name": a.name, "artifact_id": a.artifact_id, "universe": a.universe}
            for a in artifacts
        ]

    # ------------------------------------------------------------------
    # Correlation matrix across strategies
    # ------------------------------------------------------------------

    async def compute_correlation_matrix(
        self, strategies: list[dict[str, Any]]
    ) -> pd.DataFrame | None:
        """Fetch historical returns for each strategy and compute correlation."""
        returns_df = await self._build_returns_df(strategies)
        if returns_df is None:
            return None
        return returns_df.corr()

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
        """
        if not strategies:
            return []

        weights: dict[str, float] = {}
        if returns_df is not None and len(returns_df.columns) >= 1:
            vols = returns_df.std() * np.sqrt(252)
            inv_vols = 1.0 / vols.clip(lower=1e-6)
            total = inv_vols.sum()
            if total > 0:
                raw_weights = (inv_vols / total).to_dict()
                for s in strategies:
                    w = raw_weights.get(s["name"], 1.0 / len(strategies))
                    weights[s["name"]] = min(w, self._config.max_per_strategy_weight)
            else:
                for s in strategies:
                    weights[s["name"]] = 1.0 / len(strategies)
        else:
            for s in strategies:
                weights[s["name"]] = 1.0 / len(strategies)

        total_weight = sum(weights.values())
        if total_weight > 0:
            for k in weights:
                weights[k] /= total_weight

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

        returns_df = await self._build_returns_df(strategies)
        corr_matrix = returns_df.corr() if returns_df is not None else None

        weights = self.allocate_risk_parity(strategies, returns_df)

        matrix_dict: dict[str, Any] | None = None
        if corr_matrix is not None:
            matrix_dict = {
                "strategies": list(corr_matrix.columns),
                "values": corr_matrix.round(4).values.tolist(),
            }

        shock = dcc_shock_correlation(returns_df) if returns_df is not None else None

        composition = self._check_composition_gaps(weights, returns_df, corr_matrix)

        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_strategies": len(strategies),
            "strategies": strategies,
            "weights": weights,
            "correlation_matrix": matrix_dict,
            "shock_correlation": shock,
            "composition_view": composition,
        }

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
        record-outcome path, trade_plan-type artifacts only). YAML
        strategies have no outcome tracking anywhere in this codebase --
        always reported "not_tracked", never fabricated.
        """
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

        by_name = {s["name"]: s for s in base["strategies"]}
        tilted: list[dict[str, Any]] = []
        for w in base["weights"]:
            strategy = by_name.get(w["name"], {})
            confidence = await self._fetch_outcome_confidence(strategy)
            _sym = (w.get("symbol") or "").upper()
            _local = (per_symbol_regime.get(_sym) or {}).get("regime") if _sym else None
            regime_mult = self._regime_alignment_multiplier(w["name"], _local or regime)
            outcome_mult = self._outcome_confidence_multiplier(confidence)
            tilted.append({
                **w,
                "base_weight": w["target_weight"],
                "regime_multiplier": round(regime_mult, 4),
                "outcome_multiplier": round(outcome_mult, 4),
                "outcome_source": confidence.get("source"),
                "target_weight": w["target_weight"] * regime_mult * outcome_mult,
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
        self._last_weights = {t["name"]: t["target_weight"] for t in tilted}

        equity = await self._fetch_account_equity()
        if equity is not None:
            tilted = apply_position_sizing(tilted, equity, target_vol=self._config.target_volatility)

        return {
            **base,
            "weights": tilted,
            "regime": regime_info,
            "per_symbol_regime": per_symbol_regime,
            "account_equity": equity,
        }

    async def compute_daily_game_plan(self) -> dict[str, Any]:
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
        game_plan = await self.compute_daily_game_plan()
        if game_plan.get("status") == "empty":
            return game_plan

        regime = None
        if game_plan.get("regime"):
            regime = game_plan["regime"].get("regime")

        equity = game_plan.get("account_equity")
        positions = await self._fetch_positions()

        tracker = DailyPositionTracker()
        budget = compute_risk_budget(positions, equity, regime=regime, tracker=tracker)

        result = budget.to_dict()
        result["regime"] = regime
        result["game_plan_readiness"] = game_plan.get("readiness_score")
        return result
