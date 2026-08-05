---
name: structured-event-tuple-embeddings
status: candidate-not-implemented
purpose: reference note on structured event-representation research (Ding et al.) — the single most promising direction found so far. Moved here from 01-news-analysis-methods/pure-keyword-methods/ — survives Final-implementation limitation #1 only via the SRL/dependency-parsing extraction path (the "modern, simpler" LLM structured-output path does not survive).
---

# Structured Event-Tuple Embeddings — Representing "What Happened," Not "How It Feels"

## What is it

Instead of collapsing an article into a single sentiment/polarity number,
extract a **structured tuple** of who-did-what-to-whom — e.g.
`(Actor=Microsoft, Action=sues, Object=Barnes & Noble)` — and learn a
**dense vector embedding of that event itself**. Two articles about
different companies doing the same *kind* of thing (a lawsuit, an
earnings beat, a regulatory fine) end up with similar embeddings even if
they share zero words in common — something a bag-of-words or sentiment
score cannot do.

## How it works

1. **Extraction**: parse each article into an (Actor, Action, Object)
   tuple via open-domain information extraction (dependency parsing +
   semantic role labeling in the original papers — **this is the path
   that survives Final-implementation limitation #1**; the LLM
   structured-output alternative does not).
2. **Representation problem**: raw tuples are extremely sparse — too
   sparse to use directly as ML features.
3. **Embedding**: train a neural network (the original work uses a
   tensor-based neural tensor network, NTN) to map `(Actor, Action,
   Object)` into a dense vector space where semantically similar events
   land close together.
4. **Knowledge-graph enhancement** (follow-up work): jointly train the
   event embedding against a knowledge graph — reported to improve stock
   volatility prediction over event embeddings alone.
5. **Prediction**: feed the event embedding into a downstream
   classifier/regressor predicting price movement.

## Input

A single article's text at a time for the extraction/inference step
(one tuple per article). The **embedding-training step** is different:
its input is a historical corpus of many (event, subsequent price move)
pairs across articles — a batch/dataset, not a single article.

## Output format

Full version: a dense embedding vector (dimension unspecified in the
source papers) representing the `(Actor, Action, Object)` tuple, used as
a feature vector, not a human-readable label. Lower-effort partial
version (the one that survives Final-implementation's limitations): just
the raw `(Actor, Action, Object)` tuple plus a categorical event-type
tag — same output shape as `01-event-type-classification.md`, no
embedding.

## Requirements

- **Extraction step**: a dependency-parsing/SRL NLP pipeline (spaCy or
  similar) — heavier than the LLM alternative, but the one that survives
  limitation #1. Check limitation #2 against whichever SRL/parsing model
  is chosen (most spaCy pipelines are well under 2-3GB).
- **Embedding step**: requires training a small neural network on a
  labeled/aligned dataset of (event, subsequent price move) pairs — a
  real training pipeline, not a zero-shot call. Unclear yet whether this
  project's article volume for AAPL/TSLA/JNJ alone is sufficient.
- **Formula**: no closed-form formula — this is a learned representation.

## Source

Found via web search (not a local reference repo):
- Ding, Zhang, Liu, Duan. "Deep Learning for Event-Driven Stock
  Prediction." IJCAI 2015.
  https://www.ijcai.org/Proceedings/15/Papers/329.pdf
- Ding et al. "Knowledge-Driven Event Embedding for Stock Prediction."
  COLING 2016. https://aclanthology.org/C16-1201/

## Notes for future reference

- **This is the most direct answer to why the existing 3 sentiment
  methods failed.** The disproven-signal finding
  (`vinu-agent/vinu_agent/facts/seed.py`) is specifically about
  *sentiment*, not about *event structure* — this hasn't been tried here.
- **Biggest open question before building this**: does this project have
  enough historical (event, price-outcome) pairs *per ticker* to train an
  event embedder, or does it need a much larger, non-ticker-specific
  training corpus first?
- **Lower-effort partial version worth considering first**: extract just
  the (Actor, Action, Object) tuple and the **event-type category**
  *without* building the neural embedding step — i.e., treat event-type
  as a categorical feature (see `01-event-type-classification.md`) rather
  than a learned dense vector. Note this partial version, done via SRL
  parsing rather than LLM extraction, is the version that survives both
  Final-implementation limitations.
