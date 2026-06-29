"""Rule-based news enrichment matching Fincept Step 1.1 + post-enrichment NLP."""

from vinu_news.analysis.pipeline import enrich_article, enrich_batch, process_batch

__all__ = ["enrich_article", "enrich_batch", "process_batch"]
