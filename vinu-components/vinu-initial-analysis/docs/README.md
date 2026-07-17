# Correlation System Documentation

**Start at the textbook:** [**INDEX.md**](INDEX.md) — chapter-based guide for operators, researchers, and contributors.

**Architecture:** [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md)

| Guide | Description |
|-------|-------------|
| [**Textbook INDEX**](INDEX.md) | Master index: sources, engine, storage, compute, API |
| [**book/ARCHITECTURE.md**](book/ARCHITECTURE.md) | System architecture (in textbook) |

**Quick start:**

```bash
cd vinu-correlation
pip install -e ".[dev]"
cp .env.example .env
vinu-correlation-compute AAPL
vinu-correlation-query correlation AAPL
```

**Sister components:** [vinu-news](../../vinu-news/docs/INDEX.md) · [vinu-stock-price](../../vinu-stock-price/docs/INDEX.md)
