"""Cosine dedup settings (Fincept Section 5)."""

from vinu_news.analysis.config.settings_loader import get_settings

_settings = get_settings()

SIMILARITY_THRESHOLD = _settings.dedup.similarity_threshold
THREAD_MATCH_THRESHOLD = _settings.dedup.thread_match_threshold
LOOKBACK_HOURS = _settings.dedup.lookback_hours
REQUIRE_TICKER_OR_ENTITY_OVERLAP = _settings.dedup.require_ticker_or_entity_overlap
MIN_TOKEN_LEN = 2
