# News System Documentation

**Start at the textbook:** [**INDEX.md**](INDEX.md) — chapter-based guide for operators, researchers, and contributors.

**Architecture:** [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md)

| Guide | Description |
|-------|-------------|
| [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) | Single-page system diagrams (in textbook) |
| [**Textbook INDEX**](INDEX.md) | Master index: ingestion, analysis, data, API, CLI |
| [**News Derived Tables**](news_derived_tables.md) | Legacy schema/SQL reference |
| [**Component Status**](news_componete_still_missing.md) | Gaps and roadmap |

**Quick start:**

```bash
python -m vinu_news.rss.run_ingestion --once
python -m pytest vinu-news/vinu_news/analysis/tests/ vinu-news/vinu_news/rss/tests/ -v
```

**Database:** `vinu-news/vinu_news/analysis/data/news.db`
