from __future__ import annotations

import asyncio
import json
import logging
import statistics
from datetime import datetime, timezone

import httpx

from ..agent.tools import BaseTool

logger = logging.getLogger(__name__)

_TIME_TO_ANGLES = {
    "intraday": ["trend_session_structure", "trend_lifecycle", "regime_analysis", "news_price_causality"],
    "daily": ["trend_lifecycle", "regime_analysis", "drawdown_deep_dive", "news_price_causality"],
    "swing": ["trend_lifecycle", "drawdown_deep_dive", "regime_analysis"],
}

_TRANCHES_BY_STRENGTH = {
    "strong": [(1.5, 0.5), (2.5, 0.3), (4.0, 0.2)],
    "moderate": [(1.5, 0.4), (2.5, 0.3), (3.5, 0.3)],
    "weak": [(1.0, 0.33), (2.0, 0.33), (3.0, 0.34)],
}

_PRESET_BY_TIMEFRAME = {
    "intraday": "basic_ta",
    "daily": "trend_pack",
    "swing": "alpha158",
}

_INTERVAL_BY_TIMEFRAME = {
    "intraday": "15m",
    "daily": "1d",
    "swing": "1d",
}


class TradePlanTool(BaseTool):
    name = "generate_trade_plan"
    description = (
        "Generate a granular, staged trading plan document for a symbol: entry checklist, "
        "profit-booking tranches, and invalidation/exit rules. Uses existing analysis angles, "
        "quantitative factors, and backtest validation — no broker execution."
    )
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "timeframe": {
            "type": "string",
            "description": "Trading timeframe",
            "enum": ["intraday", "daily", "swing"],
        },
        "preset": {
            "type": "string",
            "description": "Feature preset recipe (optional, defaults to timeframe-appropriate preset)",
        },
        "days": {
            "type": "integer",
            "description": "Lookback days for analysis (optional, defaults to 365)",
        },
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        return asyncio.run(self._execute_async(**kwargs))

    async def _execute_async(
        self,
        symbol: str = "",
        timeframe: str = "daily",
        preset: str | None = None,
        days: int = 365,
    ) -> str:
        symbol = symbol.upper()
        initial_analysis_url = self._services_config.get("vinu_initial_analysis", "http://localhost:8083")
        tools_url = self._services_config.get("vinu_tools", "http://localhost:8082")
        simulator_url = self._services_config.get("vinu_simulator", "http://localhost:8085")
        stock_price_url = self._services_config.get("vinu_stock_price", "http://localhost:8081")

        preset = preset or _PRESET_BY_TIMEFRAME.get(timeframe, "alpha158")

        async with httpx.AsyncClient(timeout=30.0) as client:
            angles = await self._fetch_angles(client, initial_analysis_url, symbol, timeframe)

            interval = _INTERVAL_BY_TIMEFRAME.get(timeframe, "1d")
            features = await self._fetch_features(
                client, tools_url, symbol, preset, days, interval,
            )

            validation = await self._fetch_validation(
                client, simulator_url, symbol,
            )

            angles_computed = await self._symbol_has_analysis(client, initial_analysis_url, symbol)

            liquidity = await self._fetch_liquidity_check(client, stock_price_url, symbol, interval)

        return self._render_plan(symbol, timeframe, angles, features, validation, angles_computed, liquidity)

    async def _symbol_has_analysis(
        self, client: httpx.AsyncClient, base_url: str, symbol: str,
    ) -> bool:
        """Whether initial-analysis has ever computed angle data for this symbol.

        `/angle/{name}/{symbol}` returns an empty list both when the symbol has
        no analysis yet and when a specific angle genuinely has nothing to
        report, so this checks the analyzed-symbols registry directly rather
        than inferring it from empty angle payloads.
        """
        try:
            resp = await client.get(f"{base_url}/symbols")
            if resp.status_code == 200:
                symbols = resp.json().get("symbols", [])
                return symbol in symbols
        except Exception as e:
            logger.warning("Failed to check analyzed symbols for %s: %s", symbol, e)
        return False

    async def _fetch_angles(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
        timeframe: str,
    ) -> dict[str, list[dict]]:
        angle_names = _TIME_TO_ANGLES.get(timeframe, _TIME_TO_ANGLES["daily"])
        result: dict[str, list[dict]] = {}
        for name in angle_names:
            try:
                resp = await client.get(f"{base_url}/angle/{name}/{symbol}")
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    result[name] = data if isinstance(data, list) else []
                else:
                    result[name] = []
            except Exception as e:
                logger.warning("Failed to fetch angle %s for %s: %s", name, symbol, e)
                result[name] = []
        return result

    async def _fetch_features(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
        preset: str,
        days: int,
        interval: str,
    ) -> dict:
        try:
            resp = await client.post(
                f"{base_url}/requests",
                json={
                    "title": f"trade-plan-{symbol}-{preset}-{interval}",
                    "symbols": [symbol],
                    "preset": preset,
                    "days": days,
                    "interval": interval,
                    "run_immediately": True,
                },
                timeout=120.0,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch features for %s: %s", symbol, e)
        return {"status": "unavailable"}

    async def _fetch_validation(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
    ) -> dict:
        try:
            runs_resp = await client.get(f"{base_url}/runs")
            if runs_resp.status_code != 200:
                return {"status": "unavailable"}
            runs = runs_resp.json()
            if not runs:
                return {"status": "no_runs"}

            candidate = None
            for r in runs:
                codes = r.get("config", {}).get("symbols", [])
                if symbol in codes or symbol in r.get("config", {}).get("tickers", []):
                    candidate = r
                    break
            if not candidate:
                return {"status": "no_matching_run"}

            run_id = candidate.get("run_id") or candidate.get("id")
            if not run_id:
                return {"status": "no_run_id"}

            result_resp = await client.get(f"{base_url}/results/{run_id}")
            if result_resp.status_code != 200:
                return {"run_id": run_id, "status": "metrics_unavailable"}

            result = result_resp.json()
            result = result if isinstance(result, dict) else {}
            return {
                "run_id": run_id,
                "status": "available",
                "metrics": result.get("metrics", {}),
                "validation": result.get("validation", {}),
            }
        except Exception as e:
            logger.warning("Failed to fetch validation for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    async def _fetch_liquidity_check(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
        interval: str,
    ) -> dict:
        """Real volume/volatility check from recent bars — replaces the old
        hardcoded PENDING placeholder in the entry checklist.

        volume_ratio: latest bar's volume vs the trailing average — flags a
        liquidity dry-up (order would be a large fraction of a thin day).
        vol_ratio: most recent 5-bar return volatility vs the full-window
        baseline — flags trading right into an abnormal volatility spike.
        """
        try:
            resp = await client.get(
                f"{base_url}/candles/{symbol}",
                params={"interval": interval, "days": 30, "adjusted": True},
            )
            if resp.status_code != 200:
                return {"status": "unavailable"}
            bars = resp.json().get("data", [])
            if len(bars) < 6:
                return {"status": "insufficient_data", "bar_count": len(bars)}

            volumes = [float(b.get("volume", 0.0)) for b in bars]
            closes = [float(b.get("close", 0.0)) for b in bars]

            latest_volume = volumes[-1]
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
            volume_ratio = (latest_volume / avg_volume) if avg_volume > 0 else None

            returns = [
                (closes[i] - closes[i - 1]) / closes[i - 1]
                for i in range(1, len(closes))
                if closes[i - 1] != 0
            ]
            recent_returns = returns[-5:]
            baseline_std = statistics.pstdev(returns) if len(returns) >= 2 else 0.0
            recent_std = statistics.pstdev(recent_returns) if len(recent_returns) >= 2 else 0.0
            vol_ratio = (recent_std / baseline_std) if baseline_std > 0 else None

            volume_ok = volume_ratio is None or volume_ratio >= 0.3
            vol_ok = vol_ratio is None or vol_ratio <= 3.0

            return {
                "status": "available",
                "volume_ratio": volume_ratio,
                "vol_ratio": vol_ratio,
                "normal": volume_ok and vol_ok,
            }
        except Exception as e:
            logger.warning("Failed to compute liquidity check for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    def _render_plan(
        self,
        symbol: str,
        timeframe: str,
        angles: dict[str, list[dict]],
        features: dict,
        validation: dict,
        angles_computed: bool = True,
        liquidity: dict | None = None,
    ) -> str:
        lines: list[str] = []
        lines.append(f"# Trade Plan: {symbol} ({timeframe.title()})")
        lines.append(f"")
        lines.append(f"- **Generated**: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"- **Symbol**: {symbol}")
        lines.append(f"- **Timeframe**: {timeframe}")
        lines.append(f"")

        if not angles_computed:
            lines.append(
                f"> **Warning**: no initial-analysis data exists yet for {symbol}. "
                f"The structural/contextual tier (angles) below is empty, not simply "
                f"clear of findings. Run initial-analysis for this symbol first "
                f"(`POST /run/{symbol}` on initial-analysis-api) before relying on "
                f"this plan's entry/exit conditions."
            )
            lines.append(f"")

        trend_stage = self._extract_trend_stage(angles)
        tranches = _TRANCHES_BY_STRENGTH.get(trend_stage, _TRANCHES_BY_STRENGTH["moderate"])

        lines.append(f"## A. Entry Checklist")
        lines.append(f"")
        self._render_entry_checklist(lines, angles, features, trend_stage, liquidity or {})

        lines.append(f"## B. Staged Profit-Booking Tranches")
        lines.append(f"")
        self._render_tranches(lines, tranches, trend_stage)

        lines.append(f"## C. Invalidation / Exit Checklist")
        lines.append(f"")
        self._render_exit_checklist(lines, angles, validation)

        lines.append(f"## D. Supporting Data")
        lines.append(f"")
        self._render_angles_summary(lines, angles)
        self._render_features_summary(lines, features)
        self._render_validation_summary(lines, validation)

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"*Trade plan auto-generated by vinu-agent. No orders submitted.*")

        return "\n".join(lines)

    def _extract_trend_stage(self, angles: dict[str, list[dict]]) -> str:
        tl = angles.get("trend_lifecycle", [])
        if tl:
            latest = tl[-1] if isinstance(tl, list) else {}
            stage = latest.get("stage", "") if isinstance(latest, dict) else ""
            if "strong" in stage.lower() or "advancing" in stage.lower():
                return "strong"
            if "weak" in stage.lower() or "declining" in stage.lower():
                return "weak"
        return "moderate"

    def _render_entry_checklist(
        self, lines: list[str], angles: dict[str, list[dict]],
        features: dict, trend_stage: str, liquidity: dict,
    ) -> None:
        tl = angles.get("trend_lifecycle", [])
        tl_latest = tl[-1] if tl else {}
        trend_direction = (tl_latest.get("stage", "unknown") if isinstance(tl_latest, dict) else "unknown")

        lines.append(f"| # | Condition | Status | Source |")
        lines.append(f"|---|---|---|---|")

        lines.append(
            f"| 1 | Trend direction: {trend_direction} | "
            f"{'MET' if trend_stage != 'weak' else 'PENDING'} | trend_lifecycle |"
        )

        has_features = isinstance(features, dict) and features.get("status") != "unavailable"
        lines.append(
            f"| 2 | Signal confirmation from {features.get('preset', 'factors')} | "
            f"{'MET' if has_features else 'PENDING'} | vinu-tools |"
        )

        ss = angles.get("trend_session_structure", [])
        has_session = len(ss) > 0
        lines.append(
            f"| 3 | Session structure alignment | "
            f"{'MET' if has_session else 'N/A'} | trend_session_structure |"
        )

        liq_status = liquidity.get("status", "unavailable")
        if liq_status == "available":
            vr = liquidity.get("volume_ratio")
            vol_r = liquidity.get("vol_ratio")
            vr_str = f"{vr:.2f}x avg volume" if vr is not None else "volume n/a"
            vol_str = f"{vol_r:.2f}x baseline vol" if vol_r is not None else "vol n/a"
            liq_verdict = "MET" if liquidity.get("normal") else "CAUTION"
            liq_desc = f"Volume / volatility: {vr_str}, {vol_str}"
        elif liq_status == "insufficient_data":
            liq_verdict = "N/A"
            liq_desc = "Volume / volatility: insufficient bar history"
        else:
            liq_verdict = "N/A"
            liq_desc = "Volume / volatility: data unavailable"
        lines.append(
            f"| 4 | {liq_desc} | "
            f"{liq_verdict} | stock-price |"
        )

        drawdown = angles.get("drawdown_deep_dive", [])
        dd_ok = "not_in_drawdown"
        if drawdown and isinstance(drawdown[-1], dict):
            dd_val = drawdown[-1].get("drawdown_pct", 0)
            dd_ok = "caution" if abs(dd_val) > 0.15 else "normal"
        lines.append(
            f"| 5 | Drawdown context: {dd_ok} | "
            f"{'MET' if dd_ok == 'normal' else 'CAUTION'} | drawdown_deep_dive |"
        )

        lines.append(f"")

    def _render_tranches(self, lines: list[str], tranches: list[tuple[float, float]], trend_stage: str) -> None:
        lines.append(f"**Trend Strength**: {trend_stage}")
        lines.append(f"")
        lines.append(f"| Tranche | Target (R) | Fraction to Close |")
        lines.append(f"|---|---|---|")
        total_alloc = 0.0
        for i, (target_r, fraction) in enumerate(tranches, 1):
            lines.append(f"| {i} | {target_r:.1f}R | {fraction:.0%} |")
            total_alloc += fraction
        remaining = 1.0 - total_alloc
        if remaining > 0.01:
            lines.append(f"| Trail | Trailing stop from entry | {remaining:.0%} |")
        lines.append(f"")

    def _render_exit_checklist(
        self, lines: list[str], angles: dict[str, list[dict]], validation: dict,
    ) -> None:
        lines.append(f"| # | Condition | Action | Source |")
        lines.append(f"|---|---|---|---|")

        lines.append(f"| 1 | Stop-loss hit (2:1 risk/reward) | EXIT | Position sizing |")
        lines.append(f"| 2 | Trend reversal signal | EXIT | trend_lifecycle |")

        dd = angles.get("drawdown_deep_dive", [])
        has_dd = len(dd) > 0
        lines.append(
            f"| 3 | Maximum drawdown exceeded | "
            f"{'REDUCE' if has_dd else 'HOLD'} | drawdown_deep_dive |"
        )

        has_val = isinstance(validation, dict) and validation.get("status") == "available"
        lines.append(
            f"| 4 | Validation p-value below 0.05 | "
            f"{'HOLD' if has_val else 'N/A'} | monte_carlo_permutation |"
        )

        lines.append(f"| 5 | Regime shift detected | REDUCE | regime_analysis |")
        lines.append(f"| 6 | Gap against position > 2% | EXIT | price action |")
        lines.append(f"")

    def _render_angles_summary(self, lines: list[str], angles: dict[str, list[dict]]) -> None:
        sections = 0
        for angle_name, rows in angles.items():
            if rows:
                if sections == 0:
                    lines.append(f"### Angles Collected")
                    lines.append(f"")
                lines.append(f"**{angle_name}**: {len(rows)} rows")
                latest = rows[-1] if rows else {}
                if isinstance(latest, dict):
                    for k, v in list(latest.items())[:3]:
                        lines.append(f"- {k}: {v}")
                lines.append(f"")
                sections += 1

    def _render_features_summary(self, lines: list[str], features: dict) -> None:
        if isinstance(features, dict) and features.get("status") != "unavailable":
            lines.append(f"### Quantitative Features")
            lines.append(f"")
            lines.append(f"**Preset**: {features.get('preset', 'N/A')}")
            lines.append(f"**Status**: {features.get('status', 'completed')}")
            for k in ("row_count", "symbols", "interval"):
                if k in features:
                    lines.append(f"- **{k}**: {features[k]}")
            lines.append(f"")

    def _render_validation_summary(self, lines: list[str], validation: dict) -> None:
        status = validation.get("status", "unavailable")
        lines.append(f"### Backtest Validation")
        lines.append(f"")
        if status == "available":
            lines.append(f"**Run ID**: {validation.get('run_id', 'N/A')}")
            metrics = validation.get("metrics", {})
            for k in ("sharpe_ratio", "total_return", "max_drawdown", "win_rate"):
                if k in metrics:
                    v = metrics[k]
                    if isinstance(v, float):
                        if "return" in k or "drawdown" in k:
                            lines.append(f"- **{k}**: {v:.4%}")
                        elif k == "win_rate":
                            lines.append(f"- **{k}**: {v:.1%}")
                        else:
                            lines.append(f"- **{k}**: {v:.4f}")
                    else:
                        lines.append(f"- **{k}**: {v}")
            val = validation.get("validation", {})
            mc = val.get("monte_carlo", {}) if isinstance(val, dict) else {}
            if mc and isinstance(mc, dict):
                lines.append(f"- **Monte Carlo p-value**: {mc.get('p_value', 'N/A')} (min sample size met: {mc.get('minimum_met', False)})")
        elif status == "no_runs":
            lines.append(f"No backtest runs found for the symbol.")
        elif status == "no_matching_run":
            lines.append(f"No matching backtest run found.")
        else:
            lines.append(f"Validation data unavailable.")
        lines.append(f"")
