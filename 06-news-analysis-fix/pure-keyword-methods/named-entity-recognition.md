---
name: named-entity-recognition
status: candidate-not-implemented
purpose: reference note on entity-extraction (countries/orgs/people/tickers) found in the fincept-terminal reference repo, for the 06-news-analysis-fix redesign discussion — not yet evaluated or built.
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

## Requirements

- **No LLM call** — regex and dictionary lookups only, effectively free
  to run at ingest time on every article.
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
  article is about beyond the ticker(s) already tagged. This directly
  supports a richer version of **goal 3** (wording → probability) — e.g.
  "articles mentioning `Jerome Powell` + `interest_rate` category have
  historically preceded X" is a specific, testable claim this data would
  enable; a coarse `category=ECONOMIC` tag alone can't distinguish that
  from an unrelated economic story.
- Also a natural input to the **structured event-tuple** approach (see
  `structured-event-tuple-embeddings.md`) — Actor/Object slots in an
  event tuple are exactly what this entity extraction produces.
- Regex-based, not an ML NER model (spaCy, etc.) — much cheaper and
  faster, but will miss entities not in the hand-built dictionaries
  (unknown companies, non-famous executives, less common countries).
  Worth deciding upfront whether that coverage gap matters for this
  project's ticker set (AAPL/TSLA/JNJ) before choosing this over a real
  NER model.
