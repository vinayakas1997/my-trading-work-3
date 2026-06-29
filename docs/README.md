# News System Documentation

Documentation for the Fincept-style news ingestion and analysis pipeline.

| Guide | Description |
|-------|-------------|
| [**Complete Guide — News Analysis**](complete_guide_news_analysis.md) | Full architecture: ingestion, enrichment, post-processing, config, CLI, Fincept mapping, troubleshooting |
| [**News Derived Tables**](news_derived_tables.md) | SQLite schema, column reference, persist logic, SQL/Python research playbooks |
| [**Component Status**](../news_componete_still_missing.md) | What's built (~92%) vs remaining gaps (LLM, scrapers, UI, trading) |

**Quick start:**

```bash
python -m vinu_news.rss.run_ingestion --once
python -m pytest vinu-news/vinu_news/analysis/tests/ vinu-news/vinu_news/rss/tests/ -v
```

**Database:** `vinu-news/vinu_news/analysis/data/news.db`
