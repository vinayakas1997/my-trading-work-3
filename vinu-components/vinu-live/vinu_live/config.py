from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PORTFOLIO_API_URL = "http://127.0.0.1:8090"
DEFAULT_AGENT_API_URL = "http://127.0.0.1:8086"
DEFAULT_STOCK_PRICE_API_URL = "http://127.0.0.1:8081"
DEFAULT_RESEARCH_API_URL = "http://127.0.0.1:8087"
DEFAULT_INITIAL_ANALYSIS_API_URL = "http://127.0.0.1:8083"
DEFAULT_STRATEGY_API_URL = "http://127.0.0.1:8084"
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8091

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


@dataclass
class LiveConfig:
    portfolio_api_url: str = DEFAULT_PORTFOLIO_API_URL
    agent_api_url: str = DEFAULT_AGENT_API_URL
    stock_price_api_url: str = DEFAULT_STOCK_PRICE_API_URL
    research_api_url: str = DEFAULT_RESEARCH_API_URL
    initial_analysis_api_url: str = DEFAULT_INITIAL_ANALYSIS_API_URL
    strategy_api_url: str = DEFAULT_STRATEGY_API_URL
    data_root: Path = DEFAULT_DATA_ROOT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    worker_interval_sec: int = 3600
    max_slippage_pct: float = 0.001
    twap_slices: int = 6
    # "twap" (equal slices) or "vwap" (weighted by historical intraday volume
    # profile, see execution.py::compute_volume_profile) — vwap falls back to
    # equal weighting per-symbol whenever volume data is unavailable, so it's
    # always safe to select even before volume data is verified good.
    execution_style: str = "twap"
    fallback_portfolio_value: float = 1_000_000.0
    trade_plan_worker_interval_sec: int = 300
    feedback_worker_interval_sec: int = 300
    # Shadow evaluation (BENCHING -> ACTIVE promotion) doesn't need to run
    # as often as the trade-plan/feedback loops -- paper-trading Sharpe
    # only moves meaningfully over days, not minutes. 3600s matches the
    # original (pre-Phase-5) worker_interval_sec default rather than
    # inventing a new number; not independently tuned.
    shadow_worker_interval_sec: int = 3600
    # Stage 0 (G2a, research-discussion-v1/complete-plan/01-native-gaps.md):
    # scans CREATED trade_plan artifacts and calls their approve endpoint
    # (bootstrap-gated -- see trade_plan_authoring.approve_trade_plan).
    # Matches trade_plan_worker_interval_sec's own cadence rather than
    # inventing a separate number -- a freshly authored plan is worth
    # approving on roughly the same cadence it gets evaluated on.
    trade_plan_approval_worker_interval_sec: int = 300
    # Point 2's candle-close poller (reverse-engineering/
    # 03-poller-and-state-schema.md Part A) -- needs to be meaningfully
    # shorter than the shortest strategy timeframe in use so a candle
    # close is detected promptly. A guessed starting constant, same
    # posture as the other worker intervals in this file.
    live_decision_poll_interval_sec: int = 60
    # high-expectations follow-up, point #2 of 00-maturity-agentic-system-
    # explanation.md's own step-3 phasing ("risk_gatekeeper/
    # capital_allocator wiring... still not started"). Opt-in, off by
    # default, same cautious-rollout posture every other maturity-tier
    # consumer in this codebase already uses (`maturity_tier_enabled` in
    # vinu-research). Point #3's own knob (live_decision) does NOT belong
    # here -- reverse-engineering/06-execution-handoff-and-architecture.md
    # point 8 confirms the real deciding agent lives in vinu-agent, not
    # vinu-live (this service only has the poller/detector/tracker), so
    # that knob is `AgentConfig.live_decision_maturity_scaling_enabled` in
    # vinu-agent/vinu_agent/config.py instead. An earlier version of this
    # file had a same-named, unused field here -- removed once this got
    # verified rather than left as dead config.
    risk_gatekeeper_maturity_scaling_enabled: bool = False

    @classmethod
    def from_env(cls) -> LiveConfig:
        _ensure_dotenv_loaded()
        return cls(
            portfolio_api_url=os.getenv("VINU_PORTFOLIO_API_URL", DEFAULT_PORTFOLIO_API_URL),
            agent_api_url=os.getenv("VINU_AGENT_API_URL", DEFAULT_AGENT_API_URL),
            stock_price_api_url=os.getenv("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_PRICE_API_URL),
            research_api_url=os.getenv("VINU_RESEARCH_API_URL", DEFAULT_RESEARCH_API_URL),
            initial_analysis_api_url=os.getenv(
                "VINU_INITIAL_ANALYSIS_API_URL", DEFAULT_INITIAL_ANALYSIS_API_URL,
            ),
            strategy_api_url=os.getenv("VINU_STRATEGY_API_URL", DEFAULT_STRATEGY_API_URL),
            data_root=Path(os.getenv("VINU_LIVE_DATA_ROOT", str(DEFAULT_DATA_ROOT))),
            host=os.getenv("VINU_LIVE_HOST", DEFAULT_HOST),
            port=int(os.getenv("VINU_LIVE_PORT", str(DEFAULT_PORT))),
            worker_interval_sec=int(os.getenv("VINU_LIVE_INTERVAL", "3600")),
            execution_style=os.getenv("VINU_LIVE_EXECUTION_STYLE", "twap"),
            fallback_portfolio_value=float(os.getenv("VINU_LIVE_FALLBACK_PORTFOLIO_VALUE", "1000000.0")),
            trade_plan_worker_interval_sec=int(
                os.getenv("VINU_LIVE_TRADE_PLAN_INTERVAL", "300"),
            ),
            feedback_worker_interval_sec=int(
                os.getenv("VINU_LIVE_FEEDBACK_INTERVAL", "300"),
            ),
            shadow_worker_interval_sec=int(
                os.getenv("VINU_LIVE_SHADOW_INTERVAL", "3600"),
            ),
            trade_plan_approval_worker_interval_sec=int(
                os.getenv("VINU_LIVE_TRADE_PLAN_APPROVAL_INTERVAL", "300"),
            ),
            live_decision_poll_interval_sec=int(
                os.getenv("VINU_LIVE_DECISION_POLL_INTERVAL", "60"),
            ),
            risk_gatekeeper_maturity_scaling_enabled=os.getenv(
                "VINU_LIVE_RISK_GATEKEEPER_MATURITY_SCALING_ENABLED", "false",
            ).lower() in ("1", "true", "yes"),
        )


def load_config() -> LiveConfig:
    return LiveConfig.from_env()
