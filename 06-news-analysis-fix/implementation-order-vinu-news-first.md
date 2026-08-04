---
name: implementation-order-vinu-news-first
status: decided
purpose: records the user's stated understanding of the correct build order for 06-news-analysis-fix — fix/build the new enrichment columns in vinu-news first, confirm exactly what's available, then reformulate vinu-initial-analysis's angles to consume them. Confirmed correct; captured here so this isn't re-derived or second-guessed later.
---

# Build Order: `vinu-news` Enrichment First, `vinu-initial-analysis` Reformulation Second

## The decision, as stated

> "in the meaning in the project i need to understand is the just before the
> vinu-initial-analysis just from the vinu-news what columns will be ready
> so the thing i have to fix and then again re-formulate the analysis"

Confirmed correct. The dependency only goes one direction: `vinu-initial-
analysis`'s angles consume article dicts that `vinu-news` hands them —
`significance_model.py`'s `FEATURES_NUMERIC`/`FEATURES_CATEGORICAL` lists
are just field names it expects to already be populated in the data it's
given. Nothing downstream can use a column that doesn't exist upstream
yet. `sentiment_score`/`finbert_score`/`category`/`priority` are already
on the `articles` table because `vinu-news`'s `sentiment.py`/
`finbert_sentiment.py`/`category.py` write them there before
`vinu-initial-analysis` ever sees an article.

## The three steps, in order

1. **Decide + build in `vinu-news`** which of the candidate methods in
   [`methods/`](methods/AGENTS.md) become real columns on `articles` —
   event type, entity tags, triangulation count, velocity-spike flag,
   etc. This is where the actual computation happens, in the same place
   `sentiment.py`/`finbert_sentiment.py`/`category.py` already live.
2. **Confirm exactly what's available** before touching anything
   downstream — column names, types, and *when* each is populated:
   - per-article at ingest time (like FinBERT, like the proposed
     event-type/NER fields) — straightforward, same pattern as existing
     columns.
   - vs. requiring a whole-feed/batch view across many articles at once
     (like velocity-spike, which needs a rolling window across a
     category, not just the one article being enriched) — a materially
     different computation shape, not a drop-in column the same way.
3. **Only then go back to `vinu-initial-analysis`** and reformulate:
   update `significance_model.py`'s feature lists, decide whether
   `correlation.py`/`ml_model_pipeline` should consume the new columns
   too, and drop the already-disproven `sentiment_score`/`finbert_score`
   columns rather than keeping them "for more columns" (see the
   discussion in this session: more features is not automatically
   stronger, and `significance_model.py`'s own `MIN_TRAIN_POSITIVES`/
   `MIN_TEST_POSITIVES` gates exist precisely because of this risk).

## Open question flagged, not yet answered

Not yet verified: exactly how article dicts get from `vinu-news`'s
`articles` table into `vinu-initial-analysis`'s `compute(news=...)` call
— specifically, whether that's a **fixed column projection** (a new
`vinu-news` column would require updating that fetch too — a second
place to touch, not just step 1) or a **full-row passthrough** (a new
column shows up automatically once `vinu-news` writes it, no second
change needed). This determines the true scope of step 1 and needs
checking before implementation starts, not assumed either way.

## Why this file exists

To record the build-order decision explicitly, so a future session (or
agent) picking this up doesn't have to re-derive it from the discussion
history, and doesn't accidentally start by reformulating
`vinu-initial-analysis`'s angles against columns that don't exist yet.
