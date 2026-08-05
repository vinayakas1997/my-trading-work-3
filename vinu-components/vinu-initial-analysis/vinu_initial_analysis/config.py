from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from vinu_infra.config import require_data_root


def _ensure_dotenv_loaded() -> None:
    if _ensure_dotenv_loaded._done:
        return
    _ensure_dotenv_loaded._done = True
    try:
        from dotenv import load_dotenv

        for p in (Path(__file__).resolve().parent.parent, Path.cwd()):
            dotenv = p / ".env"
            if dotenv.exists():
                load_dotenv(dotenv)
                return
    except ImportError:
        pass


_ensure_dotenv_loaded._done = False  # type: ignore[attr-defined]


@dataclass(frozen=True)
class VinuInitialAnalysisConfig:
    data_root: Path = field(default_factory=lambda: require_data_root("INITIAL_ANALYSIS"))
    runs_db_path: Path = field(
        default_factory=lambda: require_data_root("INITIAL_ANALYSIS") / "vinu_initial_analysis_runs.db"
    )
    news_api_url: str = field(default_factory=lambda: os.getenv("VINU_NEWS_API_URL", "http://localhost:8080"))
    stock_api_url: str = field(default_factory=lambda: os.getenv("VINU_STOCK_API_URL", "http://localhost:8081"))
    host: str = field(default_factory=lambda: os.getenv("VINU_INITIAL_ANALYSIS_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("VINU_INITIAL_ANALYSIS_PORT", "8083")))
    cache_maxsize: int = field(default_factory=lambda: int(os.getenv("VINU_CACHE_MAXSIZE", "256")))
    cache_ttl_sec: int = field(default_factory=lambda: int(os.getenv("VINU_CACHE_TTL_SEC", "300")))
    compute_poll_interval_sec: int = field(default_factory=lambda: int(os.getenv("VINU_COMPUTE_POLL_INTERVAL_SEC", "3600")))


def load_config() -> VinuInitialAnalysisConfig:
    _ensure_dotenv_loaded()
    return VinuInitialAnalysisConfig()
