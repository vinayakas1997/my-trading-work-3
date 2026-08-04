---
name: structured-event-tuple-embeddings
status: candidate-not-implemented
purpose: reference note on structured event-representation research (Ding et al.) found via web search, for the 06-news-analysis-fix redesign discussion — the single most promising direction found so far, not yet evaluated or built.
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

This is a different task entirely from sentiment analysis: it's asking
"what category of thing just happened, structurally," not "was this
article's tone positive or negative."

## How it works

1. **Extraction**: parse each article into an (Actor, Action, Object)
   tuple via open-domain information extraction (dependency parsing +
   semantic role labeling in the original papers; an LLM structured-
   output call is a modern equivalent — see Requirements).
2. **Representation problem**: raw tuples are extremely sparse (two
   nearly-identical events with slightly different phrasing produce
   different tuples, e.g. "sues" vs "files lawsuit against") — too sparse
   to use directly as ML features.
3. **Embedding**: train a neural network (the original work uses a
   tensor-based neural tensor network, NTN) to map `(Actor, Action,
   Object)` into a dense vector space where semantically similar events
   land close together, even with different surface wording — solving
   the sparsity problem from step 2.
4. **Knowledge-graph enhancement** (follow-up work): jointly train the
   event embedding against a knowledge graph (entity relationships,
   e.g. "Microsoft is-a technology company," "Barnes & Noble is-a
   retailer") so the embedding captures not just the event but the
   *kind* of entities involved — reported to improve stock volatility
   prediction over event embeddings alone.
5. **Prediction**: feed the event embedding (for the most recent
   event(s) affecting a stock) into a downstream classifier/regressor
   predicting price movement — this replaces "sentiment_score" as a
   feature with "event_embedding" as a feature (or feature vector).

## Requirements

- **Extraction step**: either a dependency-parsing/SRL NLP pipeline
  (heavier, needs a proper parser — spaCy or similar) **or** a
  structured-output LLM call (a modern, much simpler substitute for the
  original papers' SRL pipeline: prompt the LLM to return JSON
  `{"actor": ..., "action": ..., "object": ...}` per article — this
  project already has the LLM infrastructure and the exact
  `chat_json`-style call pattern `vinu-news`'s existing
  `analyze_article()` uses, just asking a structurally different
  question than sentiment).
- **Embedding step**: requires training a small neural network (the
  tensor-based model in the original paper, or a simpler encoder) on a
  labeled/aligned dataset of (event, subsequent price move) pairs — this
  is a real training pipeline, not a zero-shot call. Needs enough
  historical (event, outcome) pairs to train on; unclear yet whether this
  project's article volume for AAPL/TSLA/JNJ alone is sufficient, or
  whether a broader (non-ticker-specific) event corpus would be needed to
  pretrain a general event embedder before fine-tuning per ticker.
- **Formula**: no closed-form formula — this is a learned representation
  (neural tensor network / knowledge-graph-joint objective), not an
  arithmetic score like the other methods in this folder.

## Source

Found via web search (not a local reference repo):
- Ding, Zhang, Liu, Duan. "Deep Learning for Event-Driven Stock
  Prediction." IJCAI 2015.
  https://www.ijcai.org/Proceedings/15/Papers/329.pdf
- Ding et al. "Knowledge-Driven Event Embedding for Stock Prediction."
  COLING 2016. https://aclanthology.org/C16-1201/

## Notes for future reference

- **This is the most direct answer to why the existing 3 methods failed.**
  Sentiment score, FinBERT, and LLM-analysis all reduce an article to a
  single valence number *before* any price comparison happens — throwing
  away exactly the structural information (who did what to whom) this
  method preserves. The disproven-signal finding in this project
  (`vinu-agent/vinu_agent/facts/seed.py`) is specifically about
  *sentiment*, not about *event structure* — this hasn't been tried here
  and isn't covered by that negative result.
- **Biggest open question before building this**: does this project have
  enough historical (event, price-outcome) pairs *per ticker* to train an
  event embedder, or does it need a much larger, non-ticker-specific
  training corpus first (pretrain on broad market news, fine-tune/apply
  per ticker)? This determines whether it's a "build it against AAPL/
  TSLA/JNJ's existing ~16k articles" project or a much bigger undertaking.
- **Lower-effort partial version worth considering first**: use an LLM
  structured-output call to extract just the (Actor, Action, Object)
  tuple and the **event-type category** (a much finer-grained version of
  this project's existing 8-bucket `category.py` keyword classifier),
  *without* building the neural embedding step — i.e., treat event-type
  as a categorical feature (like `category`/`priority` already are in
  `significance_model.py`) rather than a learned dense vector. Cheaper,
  faster to test whether event-type-conditioned outcomes actually differ
  (a simple frequency-table check) before committing to the full
  embedding-training pipeline.
