# 18 — peer_relative_strength

- **Angle id:** `peer_relative_strength`
- **Cluster:** E — Relative / cross-sectional
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/`
  (`compute.py`, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Measures how correlated this ticker's returns are with its watchlist
peers (63-bar rolling correlation) and how much it's out- or
under-performed the peer basket (20-bar relative return). **Everything
about this angle's design -- both hardcoded windows and how peer data is
fetched -- assumes daily bars.** At any of its other 5 declared
timeframes (1min through 4H), the alignment between this ticker's own
series and its peers' is likely broken (see F1) -- treat non-`1D` output
from this angle with real suspicion until that's checked.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A 63-bar rolling window approximates one calendar quarter, and a 20-bar window approximates one calendar month, of co-movement/relative-return history. | 252 trading days/year is the standard finance convention [PR1]; 63 = 252/4, 20 ≈ 252/12 |
| A2 | Peer data should always be fetched at real **daily** granularity (`interval="1D"`, hardcoded), regardless of what timeframe this angle itself is being run at. | code's own design |
| A3 | *(Implicit, not stated anywhere)* The ticker's own `bars` (fetched by the runner at whatever `time_format` this call is for) will align, timestamp-for-timestamp, with the peers' always-daily series once both are put in one DataFrame and forward-filled. | -- (this is the assumption the bug in F1 violates) |

## 3. Assumption results  *(passed to the LLM)*

Not applicable in the usual sense -- this angle's methodology (rolling
correlation, rolling relative return) is standard and doesn't rest on a
disputed literature claim the way, say, a forecasting model's
architecture does. The one external fact used is the 252-trading-day
convention behind the window sizes:

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Trading days per year, 1990-2022 average | "The average number of trading days per year from 1990 to 2022 has been exactly 252.00." | [PR1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `_aligned_closes` builds the ticker's own series from `bars` (fetched by the runner **at the requested `time_format`** -- 1min, 5min, 15min, 1H, 4H, or 1D), but fetches every **peer's** series with a hardcoded `interval="1D"`. Both get joined into one DataFrame on their raw timestamp index and forward-filled. | -- (internal, verifiable from the code alone) | **Real, serious bug for every non-`1D` timeframe.** Confirmed by tracing `runner.py`'s `_run_angle` (`bars = self._fetch_bars(symbol, tf, from_ts, to_ts)`, `tf` = the actual requested time_format) against `_aligned_closes`'s peer fetch. At `time_format="1min"`, the ticker's own series has one row per minute; every peer's series has one row per day. Joining on the raw timestamp index means almost no timestamps coincide -- a peer's single daily bar only lines up with the one minute-bar that happens to share its exact epoch second, everywhere else `ffill()` just repeats that one stale daily value across thousands of minute rows. The resulting `.rolling(63).corr(...)` is correlating the ticker's real minute-to-minute returns against a peer series that's constant for entire trading days at a time -- not a meaningful signal. |
| F2 | `spec.yaml` declares `time_formats: [1min, 5min, 15min, 1H, 4H, 1D]`, so the live orchestrator (`runner.py`) calls `compute()` at all six. | -- | This isn't a hypothetical edge case -- it's the angle's own declared, production-active configuration. Every non-`1D` run is affected by F1 as written. |
| F3 | `backtest.py`'s own module docstring describes this angle as "Group B — one row already = one trading day's close-to-close computation," with no mention of intraday variation at all, and its tagging deliberately **drops** session/subsession tags "since this angle produces exactly one row per trading day per peer, with no intraday variation to tag." | -- | **The angle's own backtest design assumes it is inherently daily-only** -- which is the correct mental model given the 63/20-bar window semantics (R1), but it directly contradicts `spec.yaml`'s declaration of 5 additional intraday time_formats. The bug (F1) and this internal inconsistency (a daily-only design paired with a multi-timeframe declaration) point at the same root cause: nothing in this angle's design was actually adapted for non-daily bars, only the time_formats list was. |
| F4 | No naive baseline; instead, `run_forward_return_validation` checks each (peer, quarter) correlation's own bootstrapped confidence interval against zero. | Reuses the same `pearson_with_ci` helper already verified correctly fixed in [16-news_price_causality-angle.md](16-news_price_causality-angle.md) (F5 there). | Sound reasoning, consistent with an already-verified-correct shared utility -- no new finding. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

One row per (sampled date, peer):

| Field | Meaning |
|---|---|
| `date`, `bar_ts` | The sampled timestamp (every 5th bar of the rolling series -- see F1 for why this is daily-meaningful only at `time_format="1D"`). |
| `peer_symbol` | Which watchlist peer this row compares against. |
| `correlation` | 63-bar rolling correlation between this ticker's and the peer's returns. |
| `relative_return_20d` | This ticker's 20-bar cumulative return minus the peer **basket's** (mean of all peers) 20-bar cumulative return over the same window. Field name says "20d" regardless of the actual bar granularity -- see F1. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| *(absent)* | Success -- rows are returned directly with no `status` field (same "success = no status key" pattern already found in `backtesting_44_metrics`). | Output fields above, one row per (date, peer). |
| `no_data` | No bars for the requested symbol. | Identification fields only. |
| `no_peers` | Watchlist has no other tickers, or none of them returned usable data. | + `n_observations`, `n_peers`. |
| `insufficient_data` | Fewer than `ROLLING_CORR_WINDOW + 2` (65) aligned bars, or a valid peer set but zero rows survived after rolling/sampling. | + `n_observations` (and `n_peers` in the first case). |

## 7. Comprehensive explanation  *(for humans only)*

**What this angle is trying to measure.** Two standard, simple relative-
strength ideas: how tightly correlated is this ticker's return stream
with its peer group right now (63-bar rolling Pearson correlation), and
has it been out- or under-performing that same peer basket over the last
20 bars (cumulative relative return). Both window sizes are chosen to
read naturally as "one quarter" and "one month" under the
standard-in-finance assumption of 252 trading days per year [PR1] --
63 = 252/4, 20 ≈ 252/12.

**Why that assumption breaks for every timeframe except `1D` (F1).**
Both windows, and the whole peer-alignment mechanism, were built and
reasoned about entirely in terms of daily bars. The code fetches peer
data as real daily candles unconditionally, but the ticker's own `bars`
come in at whatever granularity the caller actually requested -- which,
per `spec.yaml`, can be as fine as 1-minute. Once those two
different-resolution series are merged into one DataFrame keyed by raw
timestamp and forward-filled, the peer columns effectively become "the
peer's last known daily close, repeated," while the ticker's own column
retains its native intraday resolution. A 63-row rolling correlation
computed on that pairing isn't measuring "63 quarters' worth of
co-movement" or even "63 bars of anything coherent" -- it's measuring
the ticker's real minute-to-minute noise against a peer series that's
piecewise-constant across entire trading sessions.

**Why this wasn't obviously caught.** The backtest module's own
docstring shows the person who wrote it was thinking in purely daily
terms ("Group B — one row already = one trading day's close-to-close
computation") -- a correct mental model for the angle's actual design,
but one that was never reconciled with `spec.yaml`'s six-timeframe
declaration. The bug isn't in the daily-data case at all; `1D` calls
fetch both the ticker and its peers at the same real daily granularity
and align correctly. It's specifically the five other declared
timeframes where the mismatch shows up, and nothing in the code path
currently guards against or even flags it.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| PR1 | Macroption, "Trading Days per Year" | Confirms 252 as the standard trading-days-per-year convention in quantitative finance/option pricing, with a stated 1990-2022 historical average of exactly 252.00. | https://www.macroption.com/trading-days-per-year/ |
| -- | Direct trace of `vinu_initial_analysis/runner.py`'s `_run_angle`/`_fetch_bars` against `angles/peer_relative_strength/compute.py`'s `_aligned_closes` | Confirmed the ticker's own `bars` are fetched at the actually-requested `time_format`, while every peer is fetched at a hardcoded `interval="1D"` regardless of it -- the root cause of F1. | (local code read, 2026-09-24) |
