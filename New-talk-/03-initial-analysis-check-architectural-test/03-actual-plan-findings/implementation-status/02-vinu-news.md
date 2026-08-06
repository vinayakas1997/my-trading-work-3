---
name: implementation-status-vinu-news
status: in-progress
purpose: tracks real code changes made to vinu-news against 03-storage-design.md's naming/root rules.
---

# vinu-news — Implementation Status

## What's built

- **Required data root**: `vinu_news/config.py` now calls
  `require_data_root("NEWS")` instead of falling back to
  `Path.cwd()/"data"`. `VINU_NEWS_DB_PATH` (the old override var) is
  gone — db path is now always `{VINU_NEWS_DATA_ROOT}/vinu_news.db`, per
  the "no `_DB_PATH` variants" naming rule.
- **DB renamed**: `news.db` → `vinu_news.db` (code-level; see "Not yet
  done" below for what this means for the real 8MB of existing data).
- **Bug fix found and fixed along the way**: `NewsService.__init__`
  always called `load_config()` for its `AutoAnalysisWorker`'s db path
  (`vinu_news/service.py`), even when a `storage` object was passed in
  directly — two different sources of truth for "which db" that only
  coincidentally pointed at the same file before the root became
  required. Fixed to prefer the actually-injected storage's `db_path`
  when available (`getattr(self._storage, "db_path", None)`), falling
  back to config only when no storage was injected. This is a real,
  previously-latent bug: before this, code paths could silently read
  from a different db than the one the caller explicitly wired up.
- `.env` created at `vinu-news/.env` (gitignored, local-dev only) with
  `VINU_NEWS_DATA_ROOT=./data` — preserves today's actual on-disk
  behavior, just now explicit instead of an implicit code default.
- `.env-example` updated: `VINU_NEWS_DB_PATH=/data/news.db` →
  `VINU_NEWS_DATA_ROOT=/data`.

## Tested

```
87 passed, 0 failed
```

Full suite, via system Python (see note below). The dual-db-path bug fix
above was needed to get from 78 passed / 9 errors back to green — the 9
errors were `no such table: watchlist_tickers`, caused by the
auto-analysis worker silently opening a *different*, freshly-empty db
than the one the test had actually seeded.

**Environment note**: `vinu-news/.venv` is stale — `pip show` inside it
points to `C:\Users\vinay\Desktop\my-trading-work-3\vinu-news`, a
top-level path that no longer exists post-restructure (confirmed: only
`vinu-components/vinu-news` exists now). `vinu_infra` isn't even
importable in that venv. All test runs for this phase used the system
Python instead, where `vinu-infra` and all in-scope components are
correctly installed editable against their current
`vinu-components/...` paths. **The stale `.venv` folders (news,
stock-price) should probably be deleted and recreated** — flagging this,
not fixing it, since it's outside this phase's scope and not blocking
anything (system Python works fine).

## Phase 5 Section 1: the 9 news-only methods — done

New subpackage `vinu_news/analysis/methods/`, one file per method, each
exposing a real `compute`-style function per its spec file's stated
Input/Output shape. Reuse decision made per method (see
`../05-angle-reconciliation.md`'s recommendation to reuse existing NLP
code rather than rebuild):

| Method | Call | What it does |
|---|---|---|
| `event_type_classification.py` | adapt | reuses `enrichment/category.py`'s waterfall-matching pattern |
| `named_entity_recognition.py` | adapt | wraps existing `post_enrichment/ner/extract_entities.py` + `ticker_extractor.py`; added `ner/org_map.py` (the one missing dict — organizations) |
| `velocity_spike_anomaly_detection.py` | build new | no prior article-count-over-time tracking existed |
| `multi_source_triangulation.py` | adapt | reuses the existing hand-rolled TF-IDF (`cosine_dedup/vectorize.py`) instead of the spec's own crude prefix-match, per the spec's explicit recommendation |
| `tfidf_semantic_clustering.py` | adapt (near reuse) | thin wrapper around the same TF-IDF/cosine primitives |
| `vader_finance_tuned_sentiment.py` | adapt | wraps the existing `enrichment/sentiment.py` lexicon scorer with VADER's own normalization/threshold |
| `llm_sentiment_classifier_alternatives.py` | reuse-as-is | thin pass-through to the existing FinBERT scorer (non-LLM path) |
| `structured_event_tuple_embeddings.py` | build new | rule-based Actor/Action/Object extraction from NER entities + a curated verb lexicon (no spaCy/SRL dependency available) |
| `news_embedding_regime_detection.py` | build new | reuses the existing TF-IDF vectorizer as the "embedding," centroid-distance shift detection across time buckets |

**Known spec gaps, not silently dropped:** NER word-boundary matching
(spec wants to avoid "rome" inside "jerome") left as plain substring
match, matching the existing production behavior it wraps. Method 3's
168-hour rolling-count persistence has no storage table to back it —
`compute()` accepts a caller-supplied count series rather than owning
state. Method 8's neural embedding step and method 7's DeBERTa/ensemble
option are both out of scope per their own spec files' notes.
**Environment note**: `transformers` isn't actually installed in this
dev environment, so FinBERT-backed tests use `monkeypatch` rather than a
live model call — consistent with how the pre-existing 87-test baseline
already avoided exercising FinBERT directly.

No new pip dependencies — reused the project's existing hand-rolled
TF-IDF/cosine code instead of adding `scikit-learn`/`vaderSentiment`.

## Phase 6b: API redesign — done

New file `vinu_news/server/routes_v1.py`, mounted at
`/v1/stage1/vinu-news/*` alongside the existing `/news/*` routes.

**Correction to `02-api-design.md`**: that file originally said
"vinu-news doesn't need a method selector" — written before the later
decision to build the 9 Section-1 methods inside vinu-news. Now that
this component hosts multiple distinct methods, `{method}` is required
here too:
`GET /v1/stage1/vinu-news/fetch/{ticker}/{granularity}/{time-range}/{method}`.

- `fetch` is **synchronous** (unlike vinu-initial-analysis's
  trigger→poll pattern) — these methods are lightweight/live-feed
  compatible per `01-method-separation.md`, so it queries stored
  articles for the ticker/time-range and runs the method on demand, no
  separate "run" to poll for. `404`/`not_found` if no articles exist for
  that window.
- `trigger` maps onto the existing ingest pipeline
  (`NewsService.run_ticker_news_ingest`) — **known scope limitation,
  documented in the route's docstring**: that pipeline is watchlist-wide,
  not addressable per single ticker (no per-ticker ingest primitive
  exists in this codebase yet), so `trigger` refreshes the whole
  watchlist rather than truly isolating to `{ticker}`.
- `tier` is always `"tier1"` — same reasoning as vinu-stock-price's
  routes_v1.py (no tier2/tier3 distinction applies to live-feed methods).

**Real bug found and fixed while building this**: `NewsService.get_ticker_news()`
also does cross-service price-reaction enrichment (an HTTP call to
vinu-stock-price). None of these 9 text-only methods need that, and
depending on it would make every `fetch` call require vinu-stock-price
to be running — defeating the point of these being fast, standalone,
live-feed-compatible methods. The route goes straight to
`service._storage.get_news_for_ticker(...)` instead (the same query
`get_ticker_news()` itself delegates to before enrichment).

Tested: `tests/test_api_v1.py`, 14 tests (422s for bad granularity/unknown
method, 404 for no articles, all 9 methods running successfully against
seeded articles, a 3-source triangulation-confirms case, trigger→202 flow).
Full vinu-news suite: **122 passed, 0 failed** (108 baseline + 14 new).

## Not yet done

- **Real data migration**: the existing `vinu-news/data/news.db` (8MB,
  real ingested articles) is still named `news.db` on disk; the code now
  looks for `vinu_news.db`. Per your instruction not to worry about
  existing data, this is intentional — flagged so it's not a surprise,
  not fixed.
