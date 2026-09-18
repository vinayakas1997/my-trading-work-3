"""Config for the vinu-reflection worker -- deliberately minimal, no
FastAPI/server config, since this service (today) is a worker loop only,
not an HTTP API. Mirrors every other service's `load_config()` shape
(env-first, sane local-dev defaults) rather than inventing a new pattern.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReflectionConfig:
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
    worker_interval_sec: int


DEFAULT_WORKER_INTERVAL_SEC = 300


def load_config() -> ReflectionConfig:
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
    interval = int(
        os.environ.get("VINU_REFLECTION_WORKER_INTERVAL_SEC", str(DEFAULT_WORKER_INTERVAL_SEC))
    )
    return ReflectionConfig(
        data_root=data_root,
        agent_data_root=agent_data_root,
        live_trade_audit_log_path=live_trade_audit_log_path,
        screener_data_root=screener_data_root,
        portfolio_data_root=portfolio_data_root,
        worker_interval_sec=interval,
    )
