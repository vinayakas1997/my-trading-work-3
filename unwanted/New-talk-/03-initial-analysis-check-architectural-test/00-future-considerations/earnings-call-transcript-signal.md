---
name: earnings-call-transcript-signal
status: candidate-not-implemented
purpose: reference note on extracting a trading-relevant signal from earnings-call transcript text (not just the reported beat/miss number), found via web search Aug 2026 — a new data source. Parked here (moved from 03-claude-new-methods) because it fails Final-implementation limitation #1 (no LLM implementation for now).
---

# Earnings Call Transcript Signal Extraction

## Title / what it is

An LLM reads earnings-call transcripts — management's prepared remarks plus
the analyst Q&A — and extracts a trading-relevant signal (e.g. predicted
volatility, hedging/evasive language, guidance-revision cues), instead of
relying only on the numeric beat/miss figure this project's `category.py`
already tags as `EARNINGS`.

## Explanation — how it works

1. Source the transcript text (prepared remarks + Q&A) for a covered ticker's
   earnings call.
2. Feed it to an LLM (or a trained classifier, per the ECC Analyzer paper's
   approach) with structured prompts targeting a specific downstream task —
   the cited work targets **volatility prediction** directly from transcript
   content.
3. Separately, academic work asks a narrower question: does transcript
   *language* (tone, hedging, specificity) predict the sign of the
   post-announcement return, beyond what the reported numbers alone would
   predict.

## Input

A single full earnings-call transcript at a time (prepared remarks +
Q&A, one call = one input) — a long document, not a headline-length
unit.

## Output format

Depends on which paper's framing is used — the ECC Analyzer targets a
numeric **volatility prediction**; the SSRN paper's framing targets a
categorical **direction of post-announcement return** (sign only). Both
are per-transcript, not per-sentence.

## Impact — what can be extracted

Information orthogonal to both price and headline news: *how* management
talks about the quarter — confidence, hedging, evasiveness under analyst
questioning — has documented incremental signal beyond the reported beat/miss
number itself. This is a genuinely different information channel than
anything currently in `vinu-news`, which only ever sees the *headline about*
an earnings report, not the call itself.

## Is it LLM-dependent?

Yes, fundamentally. Transcripts run to thousands of words — this is a
long-document LLM task, not a keyword-rule candidate like the L1 methods
(no realistic keyword-only version of "extract hedging tone from Q&A").

**This is why it's parked here**: Final-implementation limitation #1 rules
out any LLM-dependent method for now — revisit once that limitation lifts.

## Model size / base model (from source)

Not established. The ACM page for ECC Analyzer returned a 403 (blocked from
automated fetching), and the SSRN paper wasn't checked for this detail. No
model name or size confirmed for either source — would need direct access
(e.g. an institutional login for ACM, or downloading the SSRN PDF) to fill
this in.

## Data sources needed

**Earnings call transcripts** — a new data source, not currently ingested by
vinu-news. Optionally, price around the earnings date for L3-style
validation (does the extracted tone/signal precede `ar_significant`/`car_1h`
outcomes, same discipline as everything else).

## Fit with existing project structure

Extends the **"price + earnings/fundamentals calendar"** cell already noted
in the combination matrix
(`../../00-project-understanding/01-differnt-combination-analysis.md`) — but
that entry is about *timing* (scheduled vs. surprise), while this is about
*transcript content*. Distinct enough to track as its own candidate rather
than folding into the calendar idea.

## Source

- [ECC Analyzer: Extracting Trading Signal from Earnings Conference Calls using Large Language Model for Stock Volatility Prediction](https://dl.acm.org/doi/fullHtml/10.1145/3677052.3698689)
- [Do earnings call transcripts predict post-announcement returns?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6695758) — Matéo Molinaro, SSRN
