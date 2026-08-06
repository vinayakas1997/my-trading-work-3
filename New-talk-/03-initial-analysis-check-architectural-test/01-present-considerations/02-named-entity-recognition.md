---
name: named-entity-recognition
status: candidate-not-implemented
purpose: reference note on entity-extraction (countries/orgs/people/tickers) found in the fincept-terminal reference repo. Moved here from 01-news-analysis-methods/pure-keyword-methods/ — survives both Final-implementation limitations (no LLM, no pre-trained model at all — pure regex/dictionary).
---

# Named Entity Recognition — Countries, Organizations, People, Tickers

## What is it

Extraction of structured entities (which country, which organization,
which named person, which ticker) mentioned in an article's headline and
summary — turning free text into a small set of structured tags, without
needing a full NLP entity-recognition model.

## How it works

Pure dictionary/regex lookup, no ML model:

1. **Countries**: a hand-built dictionary mapping ~200 country
   names/adjectives/capital-city names to ISO-ish codes (e.g.
   `"china"/"chinese"/"beijing" → "CN"`). Word-boundary-matched for
   short/single-word patterns (avoids `"rome"` matching inside
   `"jerome"`), plain substring match for multi-word patterns.
2. **Organizations**: similar dictionary for ~40 known
   orgs/central-banks/companies (`"the fed" → "Federal Reserve"`,
   `"nvidia" → "NVIDIA"`).
3. **People**: two paths — (a) a dictionary of ~30 known
   politicians/executives (`"musk" → "Elon Musk"`), and (b) regex
   patterns for titles (`r"\b(ceo|minister|president)\s+([A-Z][a-z]+...)"`)
   to catch names not in the dictionary.
4. **Tickers**: regex for 2-5 uppercase letters (`\b[A-Z]{2,5}\b`),
   filtered against a stoplist of common all-caps words that aren't
   tickers (`THE`, `GDP`, `CEO`, etc.).
5. Per-article results deduplicated and capped at 5 per category;
   aggregate top-10 counts returned across the whole batch.

## Input

A single article (headline + summary) at a time for the per-article
extraction; a batch of already-extracted per-article results for the
aggregate top-10 rollup step.

## Output format

A structured dict per article — lists of matched entity strings under
`countries`, `organizations`, `people`, `tickers` (deduplicated, capped at
5 each), plus an aggregate top-10 count per category across the whole
batch. No scores — presence/absence tags only.

## Requirements

- **No LLM call, no pre-trained model** — regex and dictionary lookups
  only, effectively free to run at ingest time on every article.
- **Formula**: none — pattern matching only.
- Maintenance cost: the dictionaries are hand-curated and will drift
  (new CEOs, new tickers, new geopolitical actors) — this is the real
  ongoing cost, not compute.

## Source

`personal-important/other-reference-repos/ref-fincept-terminal/fincept-qt/scripts/news_nlp.py`
— function `extract_entities()`.

## Notes for future reference

- The **ticker extraction regex is likely redundant** with whatever
  `vinu-news` already uses to populate `article_ticker_mentions` — check
  that before porting, don't duplicate.
- The **person/organization extraction is the genuinely new capability**:
  currently nothing in `vinu-news`/`vinu-initial-analysis` knows *who* an
  article is about beyond the ticker(s) already tagged.
- Also a natural input to the **structured event-tuple** approach (see
  `08-structured-event-tuple-embeddings.md`) — Actor/Object slots in an
  event tuple are exactly what this entity extraction produces.
- Regex-based, not an ML NER model (spaCy, etc.) — much cheaper and
  faster, but will miss entities not in the hand-built dictionaries.
  Worth deciding upfront whether that coverage gap matters for this
  project's ticker set (AAPL/TSLA/JNJ) before choosing this over a real
  NER model.
