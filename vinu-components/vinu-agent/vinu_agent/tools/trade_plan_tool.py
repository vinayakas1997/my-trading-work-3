from __future__ import annotations

import asyncio
import json
import logging
import statistics
from datetime import datetime, timezone, timedelta

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

_INTRADAY_SESSIONS = [
    ("Pre-market", "04:00", "09:30", "Low liquidity, gap risk — news-driven moves"),
    ("Power hour (open)", "09:30", "10:30", "Highest volume, directional bias sets tone for the day"),
    ("Midday", "10:30", "14:00", "Lower volume, range-bound — mean-reversion setups"),
    ("Power hour (close)", "14:00", "16:00", "Institutional positioning, volatility ramp"),
    ("After-hours", "16:00", "20:00", "Earnings/news driven, wide spreads"),
]


class TradePlanTool(BaseTool):
    name = "generate_trade_plan"
    description = (
        "Generate a granular, staged trading plan document for a symbol: entry checklist "
        "(long and short), profit-booking tranches, and invalidation/exit rules. Uses "
        "existing analysis angles, quantitative factors, backtest validation, news "
        "sentiment, and market regime data — no broker execution."
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
        self._last_plan_data: dict | None = None

    def execute(self, **kwargs) -> str:
        return asyncio.run(self._execute_async(**kwargs))

    @property
    def last_plan_data(self) -> dict | None:
        return self._last_plan_data

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
        news_url = self._services_config.get("vinu_news", "http://localhost:8080")
        research_url = self._services_config.get("vinu_research", "http://localhost:8087")

        preset = preset or _PRESET_BY_TIMEFRAME.get(timeframe, "alpha158")
        interval = _INTERVAL_BY_TIMEFRAME.get(timeframe, "1d")

        async with httpx.AsyncClient(timeout=30.0) as client:
            angles_task = self._fetch_angles(client, initial_analysis_url, symbol, timeframe)

            features_task = self._fetch_features(
                client, tools_url, symbol, preset, days, interval,
            )

            validation_task = self._fetch_validation(
                client, simulator_url, symbol,
            )

            angles_computed_task = self._symbol_has_analysis(client, initial_analysis_url, symbol)

            liquidity_task = self._fetch_liquidity_check(client, stock_price_url, symbol, interval)

            news_task = self._fetch_news(client, news_url, symbol)

            artifacts_task = self._fetch_active_strategies(client, research_url, symbol)

            frozen_plan_task = self._fetch_frozen_trade_plan(
                client, research_url, symbol, timeframe,
            )

            angles = await angles_task
            features = await features_task
            validation = await validation_task
            angles_computed = await angles_computed_task
            liquidity = await liquidity_task
            news = await news_task
            strategies = await artifacts_task
            frozen_plan = await frozen_plan_task

        trend_stage = self._extract_trend_stage(angles)
        trend_bias = self._extract_trend_bias(angles)
        tranches_config = _TRANCHES_BY_STRENGTH.get(trend_stage, _TRANCHES_BY_STRENGTH["moderate"])

        plan_data = self._build_structured_plan(
            symbol=symbol,
            timeframe=timeframe,
            trend_stage=trend_stage,
            trend_bias=trend_bias,
            tranches=tranches_config,
            angles=angles,
            features=features,
            validation=validation,
            liquidity=liquidity,
            news=news,
        )
        self._last_plan_data = plan_data

        markdown = self._render_plan(
            symbol=symbol,
            timeframe=timeframe,
            angles=angles,
            features=features,
            validation=validation,
            angles_computed=angles_computed,
            liquidity=liquidity,
            news=news,
            strategies=strategies,
            interval=interval,
        )

        output = markdown + "\n\n" + self._render_plan_json_block(plan_data)
        if frozen_plan.get("status") == "available":
            output += "\n\n" + self._render_frozen_plan_block(frozen_plan)
        return output

    async def _symbol_has_analysis(
        self, client: httpx.AsyncClient, base_url: str, symbol: str,
    ) -> bool:
        try:
            resp = await client.get(f"{base_url}/analysis/symbols")
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
                resp = await client.get(f"{base_url}/analysis/angle/{name}/{symbol}")
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
                f"{base_url}/features/requests",
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
            runs_resp = await client.get(f"{base_url}/simulator/runs", params={"symbol": symbol})
            if runs_resp.status_code != 200:
                return {"status": "unavailable"}
            runs = runs_resp.json()
            if not runs:
                return {"status": "no_matching_run"}

            candidate = runs[0]
            run_id = candidate.get("run_id") or candidate.get("id")
            if not run_id:
                return {"status": "no_run_id"}

            validation = candidate.get("validation")
            if validation is not None:
                return {
                    "run_id": run_id,
                    "status": "available",
                    "metrics": candidate.get("metrics", {}),
                    "validation": validation,
                }

            result_resp = await client.get(f"{base_url}/simulator/results/{run_id}")
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
        try:
            resp = await client.get(
                f"{base_url}/stock/candles/{symbol}",
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
            baseline_std = statistics.stdev(returns) if len(returns) >= 2 else 0.0
            recent_std = statistics.stdev(recent_returns) if len(recent_returns) >= 2 else 0.0
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

    async def _fetch_news(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
        limit: int = 10,
    ) -> dict:
        try:
            resp = await client.get(
                f"{base_url}/news/search",
                params={"q": symbol, "limit": limit},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return {"status": "unavailable"}
            articles = resp.json()
            if not articles:
                return {"status": "no_articles"}
            if isinstance(articles, dict):
                articles = articles.get("results", articles.get("articles", []))
            if not articles:
                return {"status": "no_articles"}
            return {"status": "available", "articles": articles}
        except Exception as e:
            logger.warning("Failed to fetch news for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    async def _fetch_active_strategies(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
    ) -> list[dict]:
        try:
            resp = await client.get(
                f"{base_url}/research/artifacts",
                params={"status": "ACTIVE,MONITORING"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return []
            artifacts = resp.json()
            return [a for a in artifacts if symbol in (a.get("universe") or [])]
        except Exception as e:
            logger.warning("Failed to fetch active strategies for %s: %s", symbol, e)
            return []

    async def _fetch_frozen_trade_plan(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        symbol: str,
        timeframe: str,
    ) -> dict:
        """Fetch the Phase 4 frozen TradePlan (forecast + risk bands + contingency rules).

        This is the only place TradePlanTool talks to the LLM-backed authoring step in
        vinu-research -- it never calls an LLM itself, it only reads the artifact
        vinu-research already froze via POST /research/trade-plan/{symbol}.
        """
        try:
            resp = await client.post(
                f"{base_url}/research/trade-plan/{symbol}",
                json={"timeframe": timeframe},
                timeout=60.0,
            )
            if resp.status_code != 200:
                return {"status": "unavailable"}
            data = resp.json()
            return {"status": "available", "artifact": data}
        except Exception as e:
            logger.warning("Failed to fetch frozen trade plan for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    def _render_frozen_plan_block(self, frozen_plan: dict) -> str:
        artifact = frozen_plan.get("artifact", {})
        return (
            "<!-- frozen_trade_plan -->\n```json\n"
            + json.dumps(artifact, indent=2)
            + "\n```\n<!-- /frozen_trade_plan -->"
        )

    # ------------------------------------------------------------------
    # Structured plan (machine-evaluable)
    # ------------------------------------------------------------------

    def _build_structured_plan(
        self,
        symbol: str,
        timeframe: str,
        trend_stage: str,
        trend_bias: str,
        tranches: list[tuple[float, float]],
        angles: dict[str, list[dict]],
        features: dict,
        validation: dict,
        liquidity: dict,
        news: dict | None,
    ) -> dict:
        direction = "short" if trend_bias == "bearish" else "long"
        direction = "neutral" if trend_bias == "neutral" else direction

        tranche_list: list[dict[str, float]] = []
        for target_r, fraction in tranches:
            tranche_list.append({"target_r": target_r, "fraction": fraction})

        entry_rules: list[dict[str, str]] = []
        entry_rules.append({
            "condition": f"trend_direction == '{self._extract_trend_stage(angles)}'",
            "status": "met" if trend_bias in ("bullish", "neutral") and trend_stage != "weak" else "pending",
            "source": "trend_lifecycle",
        })
        has_features = isinstance(features, dict) and features.get("status") != "unavailable"
        entry_rules.append({
            "condition": "signal_confirmation_from_factors",
            "status": "met" if has_features else "pending",
            "source": "vinu-tools",
        })
        liq_ok = liquidity.get("normal", False) if isinstance(liquidity, dict) else False
        entry_rules.append({
            "condition": "adequate_liquidity",
            "status": "met" if liq_ok else "caution",
            "source": "stock-price",
        })

        exit_rules: list[dict[str, str]] = []
        exit_rules.append({
            "condition": "stop_loss_hit",
            "action": "exit",
            "source": "position_sizing",
        })
        exit_rules.append({
            "condition": "trend_reversal",
            "action": "exit",
            "source": "trend_lifecycle",
        })
        exit_rules.append({
            "condition": "regime_shift",
            "action": "reduce",
            "source": "regime_analysis",
        })
        exit_rules.append({
            "condition": "gap_against_position_exceeds_2pct",
            "action": "exit",
            "source": "price_action",
        })

        contingency_rules: list[dict[str, str]] = []
        contingency_rules.append({
            "condition": "max_drawdown_exceeded",
            "action": "reduce_by_50pct",
        })
        if validation.get("status") == "available":
            contingency_rules.append({
                "condition": "validation_p_value_below_0_05",
                "action": "review_and_hold",
            })
        news_exit = False
        if news and news.get("status") == "available":
            for art in (news.get("articles") or [])[:3]:
                sentiment = art.get("sentiment", "")
                if isinstance(sentiment, str) and sentiment.lower() in ("negative", "bearish"):
                    news_exit = True
                    break
                if isinstance(sentiment, (int, float)) and sentiment < -0.3:
                    news_exit = True
                    break
        contingency_rules.append({
            "condition": "adverse_news_catalyst",
            "action": "exit" if news_exit else "monitor",
        })

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "trend_stage": trend_stage,
            "trend_bias": trend_bias,
            "tranches": tranche_list,
            "entry_rules": entry_rules,
            "exit_rules": exit_rules,
            "contingency_rules": contingency_rules,
            "position_size_pct": 0.0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _render_plan_json_block(self, plan_data: dict) -> str:
        return "<!-- structured_plan -->\n```json\n" + json.dumps(plan_data, indent=2) + "\n```\n<!-- /structured_plan -->"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_plan(
        self,
        symbol: str,
        timeframe: str,
        angles: dict[str, list[dict]],
        features: dict,
        validation: dict,
        angles_computed: bool = True,
        liquidity: dict | None = None,
        news: dict | None = None,
        strategies: list[dict] | None = None,
        interval: str = "1d",
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
        trend_bias = self._extract_trend_bias(angles)
        tranches = _TRANCHES_BY_STRENGTH.get(trend_stage, _TRANCHES_BY_STRENGTH["moderate"])

        lines.append(f"## A. Market Context")
        lines.append(f"")
        self._render_regime_context(lines, angles)
        self._render_drawdown_by_regime(lines, angles)

        lines.append(f"## B. Entry Checklist")
        lines.append(f"")
        self._render_news_sensitivity(lines, news)
        self._render_long_entry_checklist(lines, angles, features, trend_stage, trend_bias, liquidity or {})
        if trend_bias == "bearish" or trend_stage == "weak":
            self._render_short_entry_checklist(lines, angles, features, liquidity or {})
        if timeframe == "intraday":
            self._render_time_of_day_guidance(lines)

        lines.append(f"## C. Staged Profit-Booking Tranches")
        lines.append(f"")
        self._render_tranches(lines, tranches, trend_stage, trend_bias)

        lines.append(f"## D. Invalidation / Exit Checklist")
        lines.append(f"")
        self._render_exit_checklist(lines, angles, validation, news)

        lines.append(f"## E. Supporting Data")
        lines.append(f"")
        if strategies:
            self._render_active_strategies(lines, strategies)
        self._render_angles_summary(lines, angles)
        self._render_features_summary(lines, features)
        self._render_validation_summary(lines, validation)

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"*Trade plan auto-generated by vinu-agent. No orders submitted.*")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

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

    def _extract_trend_bias(self, angles: dict[str, list[dict]]) -> str:
        tl = angles.get("trend_lifecycle", [])
        if tl:
            latest = tl[-1] if isinstance(tl, list) else {}
            direction = latest.get("direction", "") if isinstance(latest, dict) else ""
            stage = latest.get("stage", "") if isinstance(latest, dict) else ""
            if "up" in direction.lower() or "bull" in stage.lower():
                return "bullish"
            if "down" in direction.lower() or "bear" in stage.lower():
                return "bearish"
            if "declining" in stage.lower():
                return "bearish"
            if "advancing" in stage.lower():
                return "bullish"
        return "neutral"

    # ------------------------------------------------------------------
    # A. Market Context
    # ------------------------------------------------------------------

    def _render_regime_context(
        self, lines: list[str], angles: dict[str, list[dict]],
    ) -> None:
        regime = angles.get("regime_analysis", [])
        if regime:
            lines.append(f"### Market Regime")
            lines.append(f"")
            latest = regime[-1] if isinstance(regime[-1], dict) else {}
            regime_name = latest.get("regime", latest.get("name", "unknown"))
            volatility = latest.get("volatility", latest.get("volatility_regime", "N/A"))
            correlation = latest.get("correlation", latest.get("avg_correlation", "N/A"))
            lines.append(f"- **Regime**: {regime_name}")
            if volatility != "N/A":
                lines.append(f"- **Volatility**: {volatility}")
            if correlation != "N/A":
                lines.append(f"- **Avg Correlation**: {correlation}")
            for k, v in latest.items():
                if k not in ("regime", "name", "volatility", "volatility_regime", "correlation", "avg_correlation"):
                    lines.append(f"- **{k}**: {v}")
            lines.append(f"")
        else:
            lines.append(f"*Regime analysis not available for this timeframe.*")
            lines.append(f"")

    def _render_drawdown_by_regime(
        self, lines: list[str], angles: dict[str, list[dict]],
    ) -> None:
        dd = angles.get("drawdown_deep_dive", [])
        if dd:
            lines.append(f"### Drawdown by Regime")
            lines.append(f"")
            lines.append(f"| Period | Drawdown | Duration | Recovery |")
            lines.append(f"|---|---|---|---|")
            for entry in dd[-5:]:
                if isinstance(entry, dict):
                    dd_pct = entry.get("drawdown_pct", entry.get("max_drawdown", "N/A"))
                    duration = entry.get("duration_days", entry.get("recovery_days", "N/A"))
                    label = entry.get("label", entry.get("period", entry.get("date", "")))
                    recovery = entry.get("recovery_status", entry.get("recovered", "N/A"))
                    if isinstance(dd_pct, (int, float)):
                        dd_str = f"{abs(dd_pct):.2%}"
                    else:
                        dd_str = str(dd_pct)
                    lines.append(f"| {label} | {dd_str} | {duration} | {recovery} |")
            lines.append(f"")

    # ------------------------------------------------------------------
    # B. Entry Checklist
    # ------------------------------------------------------------------

    def _render_news_sensitivity(
        self, lines: list[str], news: dict | None,
    ) -> None:
        if not news or news.get("status") != "available":
            return
        articles = news.get("articles", [])
        if not articles:
            return

        lines.append(f"### News Context")
        lines.append(f"")
        lines.append(f"| Date | Headline | Sentiment | Source |")
        lines.append(f"|---|---|---|---|")
        for art in articles[:5]:
            headline = art.get("title", art.get("headline", "—"))
            published = (art.get("published_at") or art.get("date") or "—")[:10]
            sentiment = art.get("sentiment", "neutral")
            source = art.get("source", art.get("provider", "news"))
            lines.append(f"| {published} | {headline} | {sentiment} | {source} |")
        lines.append(f"")
        lines.append(f"*News sentiment alert: check for earnings, FDA decisions, macro events "
                      f"that could override technical setup.*")
        lines.append(f"")

    def _render_long_entry_checklist(
        self, lines: list[str], angles: dict[str, list[dict]],
        features: dict, trend_stage: str, trend_bias: str, liquidity: dict,
    ) -> None:
        lines.append(f"### Long Entry Conditions")
        lines.append(f"")

        tl = angles.get("trend_lifecycle", [])
        tl_latest = tl[-1] if tl else {}
        trend_direction = (tl_latest.get("stage", "unknown") if isinstance(tl_latest, dict) else "unknown")
        trend_bias_ok = trend_bias in ("bullish", "neutral")

        lines.append(f"| # | Condition | Status | Source |")
        lines.append(f"|---|---|---|---|")

        lines.append(
            f"| 1 | Trend direction: {trend_direction} | "
            f"{'MET' if trend_bias_ok and trend_stage != 'weak' else 'PENDING'} | trend_lifecycle |"
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

        npc = angles.get("news_price_causality", [])
        has_npc = len(npc) > 0
        lines.append(
            f"| 6 | News/price causality alignment | "
            f"{'MET' if has_npc else 'N/A'} | news_price_causality |"
        )

        lines.append(f"")

    def _render_short_entry_checklist(
        self, lines: list[str], angles: dict[str, list[dict]],
        features: dict, liquidity: dict,
    ) -> None:
        lines.append(f"### Short Entry Conditions")
        lines.append(f"")

        tl = angles.get("trend_lifecycle", [])
        tl_latest = tl[-1] if tl else {}
        trend_direction = (tl_latest.get("stage", "unknown") if isinstance(tl_latest, dict) else "unknown")

        lines.append(f"| # | Condition | Status | Source |")
        lines.append(f"|---|---|---|---|")

        lines.append(
            f"| 1 | Trend direction: {trend_direction} | "
            f"{'MET' if 'weak' in trend_direction.lower() or 'declining' in trend_direction.lower() else 'PENDING'} | trend_lifecycle |"
        )

        ss = angles.get("trend_session_structure", [])
        has_ss = len(ss) > 0
        lines.append(
            f"| 2 | Session structure bearish bias | "
            f"{'MET' if has_ss else 'N/A'} | trend_session_structure |"
        )

        liq_status = liquidity.get("status", "unavailable")
        liq_normal = liquidity.get("normal", False) if liq_status == "available" else False
        lines.append(
            f"| 3 | Adequate liquidity for short | "
            f"{'MET' if liq_status == 'available' else 'N/A'} | stock-price |"
        )

        lines.append(
            f"| 4 | No news-driven short squeeze risk | "
            f"{'PENDING' if liq_normal else 'CAUTION'} | news analysis |"
        )

        lines.append(f"")

    def _render_time_of_day_guidance(self, lines: list[str]) -> None:
        lines.append(f"### Time-of-Day Guidance")
        lines.append(f"")
        utc_now = datetime.now(timezone.utc)
        ny_time = utc_now + timedelta(hours=-4)
        current_hour = ny_time.hour + ny_time.minute / 60

        lines.append(f"| Session | Time (ET) | Characteristics | Current? |")
        lines.append(f"|---|---|---|---|")
        for name, start_str, end_str, desc in _INTRADAY_SESSIONS:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
            start_decimal = start_h + start_m / 60
            end_decimal = end_h + end_m / 60
            is_current = "← **Now**" if start_decimal <= current_hour < end_decimal else ""
            lines.append(f"| {name} | {start_str}–{end_str} | {desc} | {is_current} |")
        lines.append(f"")
        lines.append(f"*Optimal entry zones: Power hour (open) for momentum, "
                      f"Power hour (close) for mean-reversion.*")
        lines.append(f"")

    # ------------------------------------------------------------------
    # C. Staged Profit-Booking Tranches
    # ------------------------------------------------------------------

    def _render_tranches(
        self, lines: list[str], tranches: list[tuple[float, float]],
        trend_stage: str, trend_bias: str,
    ) -> None:
        bias_label = {"bullish": "long-biased", "bearish": "short-biased", "neutral": "neutral"}
        lines.append(f"**Trend Strength**: {trend_stage}  |  **Bias**: {bias_label.get(trend_bias, 'neutral')}")
        lines.append(f"")
        lines.append(f"| Tranche | Target (R) | Fraction to Close | Direction |")
        lines.append(f"|---|---|---|---|")
        direction = "LONG" if trend_bias != "bearish" else "SHORT"
        total_alloc = 0.0
        for i, (target_r, fraction) in enumerate(tranches, 1):
            lines.append(f"| {i} | {target_r:.1f}R | {fraction:.0%} | {direction} |")
            total_alloc += fraction
        remaining = 1.0 - total_alloc
        if remaining > 0.01:
            dir_label = "Trail long" if direction == "LONG" else "Trail short"
            lines.append(f"| Trail | Trailing stop from entry | {remaining:.0%} | {dir_label} |")
        lines.append(f"")

    # ------------------------------------------------------------------
    # D. Invalidation / Exit Checklist
    # ------------------------------------------------------------------

    def _render_exit_checklist(
        self, lines: list[str], angles: dict[str, list[dict]],
        validation: dict, news: dict | None,
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

        news_exit = False
        if news and news.get("status") == "available":
            articles = news.get("articles", [])
            for art in articles[:3]:
                sentiment = art.get("sentiment", "")
                if isinstance(sentiment, str) and sentiment.lower() in ("negative", "bearish"):
                    news_exit = True
                    break
                if isinstance(sentiment, (int, float)) and sentiment < -0.3:
                    news_exit = True
                    break
        lines.append(
            f"| 7 | Adverse news catalyst | "
            f"{'EXIT' if news_exit else 'MONITOR'} | news feed |"
        )

        nlc = angles.get("news_price_causality", [])
        has_nlc = len(nlc) > 0
        lines.append(
            f"| 8 | News/price causality divergence | "
            f"{'REDUCE' if has_nlc else 'N/A'} | news_price_causality |"
        )

        lines.append(f"")

    # ------------------------------------------------------------------
    # E. Supporting Data
    # ------------------------------------------------------------------

    def _render_active_strategies(
        self, lines: list[str], strategies: list[dict],
    ) -> None:
        if not strategies:
            return
        lines.append(f"### Active Strategies")
        lines.append(f"")
        lines.append(f"| Artifact | Status | Sharpe | Type |")
        lines.append(f"|---|---|---|---|")
        for art in strategies:
            aid = art.get("artifact_id", "—")[:12]
            status = art.get("status", "—")
            sharpe = art.get("initial_sharpe", "—")
            if isinstance(sharpe, float):
                sharpe = f"{sharpe:.2f}"
            atype = art.get("type", "—")
            lines.append(f"| {aid} | {status} | {sharpe} | {atype} |")
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
