from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_FEATURES_API_URL = "http://127.0.0.1:8082"
DEFAULT_SIMULATOR_API_URL = "http://127.0.0.1:8085"
DEFAULT_CORRELATION_API_URL = "http://127.0.0.1:8083"
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_IMPROVEMENT_THRESHOLD = 0.05
DEFAULT_INITIAL_CAPITAL = 1_000_000.0
DEFAULT_DATA_ROOT = Path.cwd() / "data"

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


def _reset_env_for_testing() -> None:
    global _env_loaded
    _env_loaded = False


@dataclass
class ResearchConfig:
    features_api_url: str = DEFAULT_FEATURES_API_URL
    simulator_api_url: str = DEFAULT_SIMULATOR_API_URL
    correlation_api_url: str = DEFAULT_CORRELATION_API_URL
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    improvement_threshold: float = DEFAULT_IMPROVEMENT_THRESHOLD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    transaction_cost_pct: float = 0.001
    slippage_pct: float = 0.0005
    allow_short: bool = True
    data_root: Path = DEFAULT_DATA_ROOT


def load_config(*, force_reload: bool = False) -> ResearchConfig:
    _ensure_dotenv_loaded(force=force_reload)
    data_root_raw = os.environ.get("VINU_RESEARCH_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    return ResearchConfig(
        features_api_url=os.environ.get("VINU_FEATURES_API_URL", DEFAULT_FEATURES_API_URL),
        simulator_api_url=os.environ.get("VINU_SIMULATOR_API_URL", DEFAULT_SIMULATOR_API_URL),
        correlation_api_url=os.environ.get("VINU_CORRELATION_API_URL", DEFAULT_CORRELATION_API_URL),
        max_iterations=int(os.environ.get("VINU_RESEARCH_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS))),
        improvement_threshold=float(os.environ.get("VINU_RESEARCH_IMPROVEMENT_THRESHOLD", str(DEFAULT_IMPROVEMENT_THRESHOLD))),
        initial_capital=float(os.environ.get("VINU_RESEARCH_INITIAL_CAPITAL", str(DEFAULT_INITIAL_CAPITAL))),
        transaction_cost_pct=float(os.environ.get("VINU_RESEARCH_TRANSACTION_COST_PCT", "0.001")),
        slippage_pct=float(os.environ.get("VINU_RESEARCH_SLIPPAGE_PCT", "0.0005")),
        allow_short=os.environ.get("VINU_RESEARCH_ALLOW_SHORT", "true").lower() == "true",
        data_root=data_root,
    )
