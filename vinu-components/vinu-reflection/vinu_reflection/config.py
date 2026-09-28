"""Config for vinu-reflection.

Step 9 (system-wide-audit-and-design/00-overview.md, 02-open-questions-
strategy-and-simulation.md): `host`/`port` were deliberately absent here
("this service is a worker loop only, not an HTTP API") until a real
consumer needed to read the brain's synthesis output back. Every one of
the brain's intended consumers (Planner/vinu-agent, risk_gatekeeper/
vinu-live, capital_allocator/vinu-portfolio) is already a declared
dependency *of* vinu-reflection, so any of them importing this package
back in-process would be a real circular dependency -- an HTTP surface
is structurally required, not a style choice. Mirrors every other
service's `load_config()` shape (env-first, sane local-dev defaults)
rather than inventing a new pattern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReflectionConfig:
    #: Step 9's HTTP surface -- `serve` (cli.py), read-only, exposes only
    #: what's already durable in reflection_synthesis_outcomes (the
    #: worker loop remains the only writer).
    host: str
    port: int
    #: this service's own data root -- reflection.db (reflection_findings_
    #: history / reflection_beliefs / reflection_reference_config) lives here.
    data_root: Path
    #: where vinu-agent's llm_calls.db / team_runs.db can be read from --
    #: a *mount* of vinu-agent's own data volume (docker-compose.yml
    #: mounts it read-only), not vinu-agent's HTTP API. See
    #: vinu_reflection/reflection/decision_process.py.
    agent_data_root: Path
    #: where vinu-live's trade_audit_log.jsonl can be read from -- same
    #: mount-not-HTTP posture as agent_data_root above. See
    #: vinu_reflection/reflection/loss_attribution.py.
    live_trade_audit_log_path: Path
    #: where vinu-screener's screener_rankers.db / screener_ranker_churn.db
    #: / screener_audit.db can be read from -- same mount-not-HTTP
    #: posture. See vinu_reflection/reflection/screener_agreement.py.
    screener_data_root: Path
    #: where vinu-portfolio's allocation_history.db can be read from --
    #: same mount-not-HTTP posture. See
    #: vinu_reflection/reflection/concentration_coverage.py.
    portfolio_data_root: Path
    #: where vinu-stock-price's vinu_stock_price.db can be read from --
    #: same mount-not-HTTP posture. See
    #: vinu_reflection/reflection/ingest_health.py.
    stock_data_root: Path
    #: where vinu-initial-analysis's Parquet tree ({root}/analysis/{symbol}/
    #: {angle_name}/{granularity}/{tier}/{run_id}.parquet) can be read from
    #: -- a mount of its *data*, never an install of the package itself
    #: (torch/xgboost/chronos-forecasting/timesfm are real, unavoidable
    #: costs of installing vinu-initial-analysis, but reading its already-
    #: written Parquet files needs only pandas/pyarrow, both already
    #: transitively installed here via vinu-research/vinu-stock-price). See
    #: vinu_reflection/reflection/_initial_analysis_parquet.py.
    initial_analysis_data_root: Path
    worker_interval_sec: int
    #: Step 8 ("the brain", thinking-1/02-decided-pattern/
    #: 00-decided-pattern.md section 8) -- opt-in, off by default, same
    #: cautious-rollout posture every other maturity-tier/agentic
    #: consumer in this codebase already uses. Off means the worker loop
    #: behaves exactly as it did before this existed: 24 analysts,
    #: nothing else.
    brain_synthesis_enabled: bool
    #: How often the brain's own (LLM-calling) cycle runs, decoupled
    #: from `worker_interval_sec` (the analysts' own, much cheaper,
    #: non-LLM cycle) -- re-synthesizing on every 5-minute analyst tick
    #: would mean repeatedly re-running an LLM call over an unchanged
    #: set of active beliefs. 3600s (hourly), a guessed starting
    #: constant, same "first-pass, unvalidated" category as every other
    #: un-pinned interval in this codebase.
    brain_synthesis_worker_interval_sec: int


DEFAULT_WORKER_INTERVAL_SEC = 300
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8092


def load_config() -> ReflectionConfig:
    host = os.environ.get("VINU_REFLECTION_HOST", DEFAULT_HOST)
    port = int(os.environ.get("VINU_REFLECTION_PORT", str(DEFAULT_PORT)))
    data_root = Path(os.environ.get("VINU_REFLECTION_DATA_ROOT", str(Path.cwd() / "data")))
    agent_data_root = Path(
        os.environ.get("VINU_REFLECTION_AGENT_DATA_ROOT", str(Path.cwd() / "agent-data"))
    )
    live_trade_audit_log_path = Path(
        os.environ.get("VINU_LIVE_TRADE_AUDIT_LOG", str(Path.cwd() / "live-data" / "trade_audit_log.jsonl"))
    )
    screener_data_root = Path(
        os.environ.get("VINU_SCREENER_DATA_ROOT", str(Path.cwd() / "screener-data"))
    )
    portfolio_data_root = Path(
        os.environ.get("VINU_REFLECTION_PORTFOLIO_DATA_ROOT", str(Path.cwd() / "portfolio-data"))
    )
    stock_data_root = Path(
        os.environ.get("VINU_REFLECTION_STOCK_DATA_ROOT", str(Path.cwd() / "stock-data"))
    )
    initial_analysis_data_root = Path(
        os.environ.get(
            "VINU_REFLECTION_INITIAL_ANALYSIS_DATA_ROOT", str(Path.cwd() / "initial-analysis-data")
        )
    )
    interval = int(
        os.environ.get("VINU_REFLECTION_WORKER_INTERVAL_SEC", str(DEFAULT_WORKER_INTERVAL_SEC))
    )
    brain_synthesis_enabled = os.environ.get(
        "VINU_REFLECTION_BRAIN_SYNTHESIS_ENABLED", "false",
    ).lower() in ("1", "true", "yes")
    brain_synthesis_worker_interval_sec = int(
        os.environ.get("VINU_REFLECTION_BRAIN_SYNTHESIS_INTERVAL_SEC", "3600")
    )
    return ReflectionConfig(
        host=host,
        port=port,
        data_root=data_root,
        agent_data_root=agent_data_root,
        live_trade_audit_log_path=live_trade_audit_log_path,
        screener_data_root=screener_data_root,
        portfolio_data_root=portfolio_data_root,
        stock_data_root=stock_data_root,
        initial_analysis_data_root=initial_analysis_data_root,
        worker_interval_sec=interval,
        brain_synthesis_enabled=brain_synthesis_enabled,
        brain_synthesis_worker_interval_sec=brain_synthesis_worker_interval_sec,
    )
