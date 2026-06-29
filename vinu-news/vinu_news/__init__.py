"""vinu-news: installable news ingestion service with HTTP API."""

__version__ = "0.1.0"

__all__ = ["NewsService", "IngestionCycleResult", "__version__"]


def __getattr__(name: str):
    if name in ("NewsService", "IngestionCycleResult"):
        from vinu_news.service import IngestionCycleResult, NewsService

        return {"NewsService": NewsService, "IngestionCycleResult": IngestionCycleResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
