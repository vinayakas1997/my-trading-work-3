"""Load analysis.yaml settings with module-level cache."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "analysis.yaml"


@dataclass(frozen=True)
class DedupSettings:
    similarity_threshold: float = 0.25
    thread_match_threshold: float = 0.30
    lookback_hours: int = 48
    require_ticker_or_entity_overlap: bool = True


@dataclass(frozen=True)
class LeadPickSettings:
    prefer_recency_tiebreak: bool = True


@dataclass(frozen=True)
class ThreadSettings:
    headline_cleanup: bool = True


@dataclass(frozen=True)
class AnalysisSettings:
    dedup: DedupSettings
    lead_pick: LeadPickSettings
    threads: ThreadSettings


def _build_settings(data: dict) -> AnalysisSettings:
    dedup_raw = data.get("dedup", {})
    lead_raw = data.get("lead_pick", {})
    threads_raw = data.get("threads", {})
    return AnalysisSettings(
        dedup=DedupSettings(
            similarity_threshold=float(dedup_raw.get("similarity_threshold", 0.25)),
            thread_match_threshold=float(dedup_raw.get("thread_match_threshold", 0.30)),
            lookback_hours=int(dedup_raw.get("lookback_hours", 48)),
            require_ticker_or_entity_overlap=bool(
                dedup_raw.get("require_ticker_or_entity_overlap", True)
            ),
        ),
        lead_pick=LeadPickSettings(
            prefer_recency_tiebreak=bool(lead_raw.get("prefer_recency_tiebreak", True)),
        ),
        threads=ThreadSettings(
            headline_cleanup=bool(threads_raw.get("headline_cleanup", True)),
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> AnalysisSettings:
    """Return cached analysis settings from yaml (defaults if file missing)."""
    if not CONFIG_PATH.exists():
        return _build_settings({})
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return _build_settings(raw)


def clear_settings_cache() -> None:
    """Clear cached settings (for tests)."""
    get_settings.cache_clear()
