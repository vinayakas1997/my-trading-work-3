# Appendix C — Test Map

| Field | Value |
|-------|-------|
| **Package** | vinu-news |
| **Module** | `vinu-news/tests/` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 10 |

## Learning objectives

- Locate the test file for any vinu-news module before changing code.
- Run targeted pytest subsets by package area.
- Understand what each test file asserts at a glance.

## 1. Problem this module solves

vinu-news has **25 test files** across RSS, analysis, API, and integration paths. Contributors need a **module → test file** index to run minimal pytest scope and avoid regressions when editing a single component.

## 2. Position in pipeline

```mermaid
flowchart LR
  Code[vinu_news module] --> Test[tests/ file]
  Test --> CI[pytest]
  CI --> Confidence[Safe refactor]
```

| Step | Input | Output |
|------|-------|--------|
| Edit module | e.g. `filter.py` | Run mapped test file |
| Full verify | `pytest tests/` | All 25 files |

## 3. File map

| Directory | Count | Scope |
|-----------|-------|-------|
| `tests/rss/` | 5 | Fetch, parse, health, pipeline |
| `tests/analysis/` | 14 | Enrichment, post-process, persist, FTS |
| `tests/` (root) | 10 | API, CLI, filter, providers, LLM, price |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| Module path | string | yes | `collection/filter.py` |
| pytest marker | string | no | `-k feed_health` |

### Output

| Field | Type | Example |
|-------|------|---------|
| Test file path | string | `tests/test_filter.py` |
| Key assertions | list | ticker mode filtering |

## 5. Logic (step by step)

1. Identify the module you changed (see chapter File map).
2. Look up test file in tables below.
3. Run `pytest vinu-news/tests/<file> -v` from repo root.
4. Before PR, run full suite: `pytest vinu-news/tests/ -v`.
5. Windows: always close `NewsRepository` / `NewsService` in fixtures.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `tmp_path` | pytest fixture | per test | Isolated SQLite DBs |
| `monkeypatch` | pytest | — | Mock HTTP/LLM |

## 7. Worked examples

### Example A — happy path (after editing sentiment.py)

```bash
cd vinu-news
pytest tests/analysis/test_enrichment.py -v
```

### Example B — edge case (RSS only)

```bash
pytest tests/rss/ -v
```

### Example C — TASK integration tests

```bash
pytest tests/test_llm_analyze.py tests/test_ticker_news_provider.py \
       tests/test_price_reaction.py tests/test_watchlist_sync.py -v
```

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| CLI | `pytest vinu-news/tests/ -v` | — | Full suite |
| CLI | `pytest vinu-news/tests/test_api.py -v` | — | HTTP routes |

## 9. SQL / queries (if applicable)

Tests use temporary SQLite files — no production DB queries required.

## 10. Tests

### Root tests (`vinu-news/tests/`)

| Test file | Module under test | Asserts |
|-----------|-------------------|---------|
| `test_api.py` | `server/` routes | Health, settings, watchlist, search, UI |
| `test_cli_continuous.py` | `cli.py` | `--continuous` uses DB poll interval |
| `test_filter.py` | `collection/filter.py` | Ticker vs all mode, empty watchlist |
| `test_ingest_filter.py` | `service.py` + filter | End-to-end ticker persist |
| `test_settings_watchlist.py` | `settings/`, `watchlist/`, `storage/` | CRUD, env seed, factory |
| `test_watchlist_sync.py` | `watchlist/shared.py` | TASK-X01 shared JSON merge |
| `test_ticker_news_provider.py` | `providers/` | TASK-N02 registry mock fetch |
| `test_llm_analyze.py` | `analysis/llm/` | TASK-N01 cache + mock LLM |
| `test_price_reaction.py` | `price_reaction.py` | TASK-N03 percent math |

### RSS tests (`tests/rss/`)

| Test file | Module under test | Asserts |
|-----------|-------------------|---------|
| `test_feed_health.py` | `rss/storage/feed_health.py` | Success/failure streaks |
| `test_response_validator.py` | `rss/fetch/response_validator.py` | HTML cloaking, short body |
| `test_rss_parser.py` | `rss/parse/rss_parser.py` | Entry parsing, link required |
| `test_ingestion_pipeline.py` | `rss/orchestration/` | Mocked HTTP, fail-soft, DB insert |

### Analysis tests (`tests/analysis/`)

| Test file | Module under test | Asserts |
|-----------|-------------------|---------|
| `test_enrichment.py` | `enrichment/*` | All 9 stages, Fincept examples |
| `test_url_dedup.py` | `pre_enrichment/url_dedup.py` | First link wins |
| `test_post_process.py` | `post_enrichment/post_process.py` | Dedup clusters, skip flag |
| `test_headline_cleanup.py` | `headline_cleanup.py` | Prefix stripping |
| `test_synonyms.py` | `synonyms/synonym_map.py` | Word normalization |
| `test_ner.py` | `post_enrichment/ner/` | Entity extraction |
| `test_cosine_dedup.py` | `cosine_dedup/` | Similarity clustering |
| `test_cluster_gates.py` | `lead_pick/` gates | Beat vs miss separation |
| `test_recency_lead.py` | `lead_pick/scoring.py` | Recency tie-break |
| `test_thread_matcher.py` | `storage/threading/matcher.py` | Cross-batch match |
| `test_persist.py` | `storage/persist.py` | Threads, snapshots, URL skip |
| `test_fts.py` | `storage/fts.py`, `repository.search_articles` | FTS after insert |

### Module → test quick lookup

| Module | Primary test file(s) |
|--------|---------------------|
| `rss/fetch/` | `test_response_validator.py`, `test_ingestion_pipeline.py` |
| `rss/storage/feed_health.py` | `test_feed_health.py` |
| `providers/` | `test_ticker_news_provider.py` |
| `collection/filter.py` | `test_filter.py`, `test_ingest_filter.py` |
| `analysis/enrichment/` | `test_enrichment.py` |
| `analysis/llm/` | `test_llm_analyze.py` |
| `analysis/post_enrichment/price_reaction.py` | `test_price_reaction.py` |
| `analysis/storage/persist.py` | `test_persist.py` |
| `analysis/storage/fts.py` | `test_fts.py` |
| `watchlist/shared.py` | `test_watchlist_sync.py` |
| `service.py` | `test_ingest_filter.py`, `test_api.py` |
| `server/` | `test_api.py` |

## 11. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `database is locked` | Open connection on Windows | Close repo in fixture teardown |
| Mock HTTP test fails | URL changed | Update mock in test file |
| FTS test flaky | Trigger timing | Use `repo.init_schema()` fresh DB |
| Import error | Wrong cwd | Run from `vinu-news/` with editable install |

## 12. Fincept / reference repo mapping

| Fincept reference | Implementation |
|-------------------|----------------|
| `test_enrichment.py` | Mirrors `step_1_1_news.md` worked examples |
| Integration tests | End-to-end Fincept Step 1 path |

## 13. Related chapters

- [Chapter 10 — Pipeline Overview](../part-2-analysis/ch10-pipeline-overview.md)
- [Appendix B — Troubleshooting](apx-b-troubleshooting.md)
- [Appendix D — Roadmap & Gaps](apx-d-roadmap-gaps.md)
- [Chapter 00 — Preface](../part-0-getting-started/ch00-preface.md) (contributor path)
