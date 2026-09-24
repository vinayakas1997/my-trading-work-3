# 28 — trend_session_structure

- **Angle id:** `trend_session_structure`
- **Cluster:** F — Pattern history & lifecycle
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_session_structure/`
  (`compute.py`, `sessions.py`, `spec.yaml`; no independent peak detection --
  reads `trend_lifecycle`'s stored snapshots directly)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Reads `trend_lifecycle`'s already-stored peak/trough snapshots and
breaks them down by trading session (premarket/regular/afterhours) --
which session tends to produce reliable tops, with per-session
drawdown/recovery/match-similarity stats. Deliberately reuses
`trend_lifecycle`'s peak detection rather than duplicating it ("Option
A: single source of truth"). **Silently returns `not_applicable` at 2 of
its 5 declared timeframes** (see F1) -- and even where it wouldn't, its
one upstream dependency has its own real gap at those exact timeframes
(see F2, cross-referencing [27-trend_lifecycle-angle.md](27-trend_lifecycle-angle.md)).

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Session-level breakdown (premarket/regular/afterhours) is only meaningful at **intraday** resolution -- on 1D+ bars, every peak lands in exactly one session bucket, so a breakdown there would be an artifact, not a real finding. | code's own docstring |
| A2 | Rates/averages built from fewer than 10 mature peaks in a session are unreliable and should be suppressed (`None`), not reported as if they were real signal. | code's own design (`_MIN_SAMPLE = 10`) |

## 3. Assumption results  *(passed to the LLM)*

Not applicable in the disputed-literature sense -- this angle is a pure
downstream aggregation of `trend_lifecycle`'s already-detected peaks, so
its findings are internal-consistency findings, not claims against
external sources.

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `_INTRADAY_FORMATS = {"15min", "1H", "4H"}`. `spec.yaml` declares this angle's `time_formats` as `[1min, 5min, 15min, 1H, 4H]`. Any call with `time_format` not in `_INTRADAY_FORMATS` returns `status: "not_applicable"` immediately, with zero session analysis attempted. | -- (internal, verifiable from the code alone) | **Real, confirmed gap.** `1min` and `5min` are declared as supported timeframes in `spec.yaml` but are silently excluded from the actual intraday-format check -- every call at those two timeframes returns `not_applicable`, the same status meant for genuinely inapplicable daily-and-above timeframes (per A1), even though 1-minute/5-minute data is exactly where premarket/regular/afterhours session structure would be most granular and potentially most informative. |
| F2 | This angle has no peak detection of its own -- it reads `trend_lifecycle`'s stored snapshots for the matching `time_format`. | [27-trend_lifecycle-angle.md](27-trend_lifecycle-angle.md)'s F1/F2: `trend_lifecycle`'s own peak-drop threshold table is missing `1min`/`5min` entries, silently falling back to a `1H`-scale threshold (-3%) that an ATR floor cannot loosen. | **Compounding gap.** Even if this angle's own `_INTRADAY_FORMATS` set were corrected to include `1min`/`5min`, it would very likely still land on `no_upstream_data` at those timeframes, because its one upstream dependency rarely detects any peaks there at all. Fixing either bug alone wouldn't be enough to make session-structure analysis actually work at 1-minute/5-minute resolution -- both would need to be fixed together. |
| F3 | `dedup_latest_snapshots` keeps only the newest-`stored_at` row per `(inflection_type, bar_ts)`, specifically because `trend_lifecycle` re-captures immature snapshots on later runs as their outcome finalizes. | -- | **Correct, careful handling** of a real data-shape consequence of how `trend_lifecycle` writes its own history -- verified by cross-reading both modules together, not assumed from one file's comment alone. |
| F4 | Session-level rates/averages are suppressed below `_MIN_SAMPLE=10` mature peaks per session; raw counts are always shown regardless. | -- | Consistent with the same "never present a rate without enough sample behind it" discipline already found across `pnl_attribution`, `news_price_causality`, and `shock_clustering` in this folder. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

One row per session (`premarket`/`regular`/`afterhours`/`closed`) plus one summary row:

| Field | Meaning |
|---|---|
| (per-session rows) | Peak/trough counts, drawdown/recovery stats (suppressed below `_MIN_SAMPLE`), match-similarity stats attributed via each match's queried peak's session. |
| `type: "summary"` | `total_peaks`, `total_troughs`, `n_sessions_with_data`, `n_qualifying_sessions` (met `_MIN_SAMPLE`), `best_session`, `worst_session`. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` (on the `summary` row) | Meaning |
|---|---|
| *(normal completion)* | Session rows + summary computed from upstream snapshots. |
| `not_applicable` | `time_format` isn't `15min`/`1H`/`4H` -- **includes `1min`/`5min` despite `spec.yaml` declaring them as supported (F1)**, as well as genuinely-inapplicable `1D`+ formats. |
| `no_upstream_data` | No usable `trend_lifecycle` snapshots found for this symbol/timeframe -- the likely outcome even if F1 were fixed, per F2. |

## 7. Comprehensive explanation  *(for humans only)*

**A clean, deliberate downstream design.** This angle's core decision --
read `trend_lifecycle`'s already-detected peaks rather than re-running
peak detection -- is a sound "single source of truth" choice, avoiding
the risk of two independently-drifting peak definitions in the same
codebase (the exact kind of drift `regime_analysis`'s own docstring
describes fixing elsewhere). Deduplication and mature-outcome filtering
are both handled carefully, cross-verified against how `trend_lifecycle`
actually writes its snapshot history.

**The timeframe gap, and why it's worse than it first looks (F1/F2).**
Taken alone, `_INTRADAY_FORMATS` missing `1min`/`5min` is a simple,
easily-fixed oversight -- add the two strings to the set. But this
angle's entire value depends on `trend_lifecycle` having already
detected real peaks at that timeframe, and `trend_lifecycle` itself
(researched immediately before this angle) has its own, independent gap
at exactly the same two timeframes. The two bugs happen to point at the
same outcome (no useful session-structure signal below 15-minute
resolution) via two different mechanisms -- one an explicit exclusion in
this angle, one a threshold miscalibration one layer upstream. Neither
fix alone would be sufficient; both would need correcting together for
1-minute/5-minute session-structure analysis to actually produce
anything.

**Closing note for this research pass.** Across the 6 angles most
affected by timeframe-handling issues in this folder --
`peer_relative_strength`, `regime_analysis`, `shock_clustering`,
`shock_personality`, `trend_lifecycle`, and this one -- the same root
pattern recurs: components built and reasoned about in daily (or
1-hour-and-up) terms, later declared across a wider `time_formats` list
without every fixed threshold, constant, or lookup table being
re-examined for the finer resolutions added. This angle's version of
that pattern is among the most direct to state precisely: two declared
timeframes, one missing set entry, one compounding upstream cause.

## 8. Citations

No external sources were needed for this angle -- every finding here is
a direct, internal cross-reference between this module's own code and
`trend_lifecycle`'s (already researched and cited in
[27-trend_lifecycle-angle.md](27-trend_lifecycle-angle.md)), verified by
reading both files together.

| id | Source | What was used | Link |
|---|---|---|---|
| -- | Direct read of `vinu_initial_analysis/angles/trend_session_structure/compute.py`'s `_INTRADAY_FORMATS` set against `spec.yaml`'s `time_formats` list | Confirmed `1min`/`5min` are declared but excluded from the intraday check (F1). | (local code read, 2026-09-24) |
