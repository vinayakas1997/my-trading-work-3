"""Orchestration package."""

from vinu_news.rss.orchestration.ingestion_pipeline import (
    IngestionSummary,
    run_ingestion,
)

__all__ = ["IngestionSummary", "run_ingestion"]
