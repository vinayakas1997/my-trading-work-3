# Decided: how "a big move" gets defined numerically

**Decided (2026-09-25, recorded as Decision 14 in `../01-planning.md`):
ATR-multiple, starting at 2×ATR(14).** This file's trade-off writeup is
kept below as the record of why, and to keep the door open on the
multiplier value (2.5×, 3× etc.) once real recorded moves exist to check
2× against.

## Why a flat fixed percentage (the user's original ~1.5% idea) is worth reconsidering

A fixed threshold applied identically to every ticker means something
different everywhere: 1.5% is a huge move for a sleepy utility stock and
completely unremarkable for a volatile small-cap or biotech. The same
number silently means "significant" for one ticker and "noise" for
another.

## The three real options, with trade-offs

### 1. ATR-multiple (recommended)
A move counts as "big" when it exceeds some multiple of the ticker's own
ATR(14) — e.g. `move > 2 × ATR(14)`.
- **Why it's the recommendation**: this is the actual industry-standard
  approach for exactly this problem. Breakout/trend systems (Chandelier
  Exits, Donchian-ATR breakout systems) are built on this same idea.
  Self-normalizes per ticker automatically — no separate calibration
  needed per symbol.
- Already has a real precedent in this codebase's own design: `atr_14`
  is one of the 52 indicators already implemented and computed by
  `signal_evidence` today (via `vinu_tools`), so reusing it here isn't
  new infrastructure.
- Interpretable: "this move was 2.5× a typical day's range" is a
  meaningful, explainable number.

### 2. Return z-score
A move counts as "big" when its return exceeds roughly 2 standard
deviations of the ticker's recent return distribution.
- Same normalizing spirit as ATR-multiple, slightly different math
  (distribution-based rather than range-based).
- Common in stat-arb / regime-detection work specifically.
- Slightly more sensitive to the *shape* of the return distribution
  (fat tails, skew) than ATR, which is purely range-based.

### 3. Rolling percentile
A move counts as "big" when it's in, say, the top 10% of that ticker's
own moves over a trailing window (e.g. the last 60 or 90 days).
- Fully adaptive — automatically recalibrates as a ticker's volatility
  regime changes over time (e.g. before/after an earnings-driven
  volatility shift).
- Needs meaningfully more history before it's trustworthy (a percentile
  computed from too few historical moves is unstable) — a real cost the
  other two options don't have.

## Decision, restated plainly

ATR-multiple, starting at **2×ATR(14)**. It's the simplest of the three
volatility-relative options, has a direct, already-implemented indicator
to build on, and is the closest match to established, well-understood
practice for this exact kind of detection.

## Still open

- The multiplier's exact final value — `2×ATR` is the deliberate
  starting point, not permanently fixed; `2.5×` and `3×` remain live
  comparison points/bins once real recorded moves exist to check 2×
  against — same class of problem as `FORWARD_HORIZON_BARS` in Track 1: a
  guessed constant until there's real data to derive it from properly.
- The window the ATR itself is computed over (14 bars is assumed, to
  match Track 1's existing `ADX_PERIOD`/`RSI_PERIOD` conventions, but not
  explicitly re-confirmed as a deliberate choice yet).
