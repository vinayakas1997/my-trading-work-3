---
name: angle-validation-checklist
status: decided
purpose: the repeatable procedure every future angle's walk-forward backtest wiring must pass before being called done — real market data (not synthetic), every declared timeframe, and a fixed set of checks — so the shared infrastructure doesn't silently break on a real angle later the way a synthetic-data-only check would miss.
---

# Angle Validation Checklist — Real Data, Every Timeframe

## Why this exists

DLinear's first end-to-end check (see `implementation-summary.md` §2) used a
synthetic random-walk price series. That was enough to prove the *plumbing*
— shapes, wiring, round-trips — but a random walk can't produce a real
weekend gap at the right calendar position, a real NYSE holiday, a real
DST transition, or real pre-market/after-hours activity. It also only
checked DLinear's one declared timeframe. Both gaps were checked directly
(see "What this actually caught" below) and both turned up real,
non-obvious behavior that synthetic data had been silently hiding. This
file is the fix: the checklist every angle's backtest wiring must go
through before being marked done, using real data, covering every
timeframe the angle declares.

## The rules

1. **Real market data, not synthetic.** Fetch through the project's real
   ingestion path when the local price service (`vinu-stock-price`,
   `VINU_STOCK_API_URL`) is running — that exercises the actual interval
   mapping and chunking `PriceClient` does in production. When that
   service isn't running (e.g. local dev), fetching directly from a real
   provider (confirmed working here: `yfinance`, no API key needed) is an
   acceptable fallback for this check, but it bypasses `PriceClient`'s own
   glue — note which path was used when recording the check, don't present
   a `yfinance`-only check as equivalent to going through the real service.
2. **Small window is fine — but it must be real.** There's no need for the
   full multi-year history; `min_observations + ~20 steps` worth of real
   calendar time is enough to exercise the loop meaningfully. A few months
   of real daily data, or a few days of real intraday data, is enough.
3. **Every timeframe the angle declares in its `spec.yaml`, independently.**
   Different timeframes are not interchangeable checks of the same thing —
   a daily bar's timestamp sits at midnight and never lands inside any
   real trading session; an intraday bar's timestamp does, and only
   intraday data exercises the premarket/regular/afterhours tagging paths
   at all (see finding #1 below). Passing on `1D` proves nothing about
   `15min`.
4. **When fetching intraday data from a provider, explicitly request
   pre/post-market bars.** Most providers (confirmed: `yfinance`) return
   regular-hours-only bars by default — a check that doesn't ask for
   pre/post data will silently never exercise the premarket/afterhours
   code paths and report false confidence (see finding #2 below).

## The checklist itself

For each `(angle, timeframe)` pair:

1. **Bar sanity** — `bar_ts` is sorted ascending, no duplicates, and the
   gaps between consecutive bars look like real calendar gaps for that
   timeframe (e.g. a 1D series should show >1-day gaps at real weekends
   and holidays, not a suspiciously uniform spacing).
2. **Row-count check** — the backtest's output row count matches the
   formula (`len(bars) - min_observations - horizon + 1`), not just "some
   rows came out."
3. **Tag spot-check** — pick a handful of output rows, including at least
   one immediately after a real multi-day gap (a weekend or holiday), and
   confirm their tags match `tag_row()` called standalone on the same
   `bar_ts`.
4. **Weights check, if the angle trains a model** — don't just confirm the
   file unpickles. Reload the `state_dict`, rebuild the model, and
   reproduce that step's own recorded forecast from it. If the reloaded
   model doesn't reproduce the same number, the wrong model (or the wrong
   step's data) got saved.
5. **Storage round-trip** — write through the real `AngleStorage`, read
   back, confirm row-for-row equality.
6. **Query layer check** — run at least one real `query_slice` grouping
   and hand-verify one group's number against a manual pandas `groupby`
   on the same output. Pick a grouping that's actually meaningful for the
   timeframe (see finding #1 — don't group 1D-or-coarser results by
   `session`, it will trivially all be `"closed"`; group by `day_of_week`/
   `month`/`quarter` instead for those).
7. **Delete-cleanup regression check** — run `delete_angle` and confirm
   both storage trees and the `RunLog` rows are actually gone.

## What this actually caught, running it for real

Run against 186 real daily AAPL bars (2025-11-10 to 2026-08-07, fetched
via `yfinance` since the local price service wasn't running) through
DLinear's real backtest wiring — full results in the terminal session, two
things worth recording permanently:

**Finding #1 — daily bars tag as `session="closed"`, always, and that's
correct, not a bug.** A 1D bar's timestamp sits at midnight UTC, which
`_market_hours.py`'s classifier correctly reports as outside every real
trading session. This isn't new — `04-enhancement-of-each-angle/
31-trend_session_structure.md` already documented that 1D+ timeframes
should return `not_applicable` for session breakdowns rather than compute
one — but this check reconfirmed it concretely against real timestamps,
and it's the reason rule 4/checklist-item-6 above exists: a session-grouped
query example for a daily-only angle would look "correct" (one group, a
real number) while actually being a meaningless artifact.

**Finding #2 — a naive intraday fetch silently only returns regular-hours
bars.** A first pass at fetching 5 days of real 15-minute AAPL bars came
back 100% `session="ny", subsession="markethours"` — not because the
tagging code was wrong, but because the default `yfinance` intraday fetch
excludes pre/post-market data entirely. Re-fetching with `prepost=True`
produced a real, varied distribution (`ny/markethours`, `ny/premarket`,
`ny/afterhours`, `london`) across the same 5 days. A validation check built
on the first fetch would have "passed" while never actually exercising
three of the five session/subsession values the tagging code produces —
which is exactly the false-confidence failure mode this whole checklist
exists to prevent going forward.

## How this applies to what comes next

ARIMA is next in the build order (per `plan.md`). Its `spec.yaml` declares
more than one timeframe, so it's the first angle where checklist rule 3
(every timeframe, independently) actually has more than one timeframe to
apply to — that's the point where this checklist gets exercised for real,
not just DLinear's single-timeframe case.

## Related files

- `plan.md` — the infrastructure this checklist validates.
- `implementation-summary.md` — records what was built and the (weaker,
  synthetic-data) check that was originally done; this file supersedes
  that check's data source, not its structural findings.
- `04-enhancement-of-each-angle/31-trend_session_structure.md` — where the
  "1D+ session tagging is an artifact" fact was first documented.
