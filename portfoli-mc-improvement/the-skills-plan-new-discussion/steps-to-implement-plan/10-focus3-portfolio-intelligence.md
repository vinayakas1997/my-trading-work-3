---
name: 10-focus3-portfolio-intelligence
status: In Progress
phase: 5
code: A3
depends_on: []
unlocks: []
---

# Step 10 — Focus 3: Progressive Daily Portfolio Intelligence

## Why this step

This is the third original aim, deliberately kept as a separate track from
day one — it doesn't block, and isn't blocked by, the Focus 1/2 work above.
`vinu-portfolio` turned out to already have real operational infrastructure
(`PortfolioDrawdownMonitor`, `drawdown_scheduler.py`) — the original
"stateless, no tracking" framing from the first planning pass was only
half right. What's actually still missing, confirmed by reading
`vinu_portfolio/service.py`, is the allocation *intelligence* itself:
`build_portfolio()` is a stateless risk-parity calculation off a
correlation matrix — no regime-awareness, no memory of yesterday's
outcomes, no probability model.

## What we're achieving

A daily allocation process that: reads current market regime from
`vinu-initial-analysis`'s angles (via `AngleRunner`'s already-systematic
execution — Focus 2's consumption gap applies here directly), reads
yesterday's actual performance, reads active strategies from
`vinu-strategy`'s registry (Step 04's tags may help here too — regime-aware
strategy selection is the same alignment-matching problem in a different
context), and produces a probability-weighted allocation (tickers + cash
ratio) that's expected to improve as outcomes accumulate over time.

## Where it matters in the future

This is the most ambitious and highest-value piece of the original three
Focus areas — it's what turns the platform from "computes good strategies"
into "actually runs money well, and gets better at it." It's also the
least immediately actionable right now, since it depends on Focus 1/2's
outputs existing and being trustworthy first (a portfolio built on
unvalidated strategies is not an improvement).

## How it connects to other steps

- **Genuinely independent of Steps 01–09 for its own design work** — can
  be scoped and designed in parallel with everything above.
- **Practically benefits from Focus 1/2 being real first** — the
  "strategies" and "yesterday's performance" this step reads should
  ideally already be running through the gatekeepers (Step 03) and sweep
  (Step 06/07) machinery, or this step is building intelligence on top of
  unvalidated inputs.
- **Depends on Step 09** for knowing exactly where the existing safety net
  (promotion bar, circuit breaker) starts and ends before adding capital
  allocation logic on top of it. **Step 09 is done** —
  `project-understanding/skills/live-safety/SKILL.md` documents the real
  four-stage chain. The load-bearing fact for this step specifically: an
  ACTIVE artifact today has cleared the research promotion bar (Stage 1)
  but has **never** been checked against real paper-trading performance
  (Stage 2, `ShadowEvaluator`, confirmed built but never invoked by
  anything). Do not design this step's allocation weighting to treat every
  ACTIVE strategy as equally trusted — that silently inherits a gap this
  step didn't create but would otherwise propagate into real capital
  decisions. Either account for the gap explicitly (e.g. weight by
  something Stage 2 would have provided if it ran) or treat closing Stage
  2 as a prerequisite, not an assumption.
- **Reuses Step 04's tag/alignment concept** — regime-aware strategy
  selection for the daily allocation is structurally the same problem as
  "find a strategy aligned with this regime," just applied at the
  portfolio level instead of the single-strategy level.

## Substeps

*(This step is intentionally left less detailed than 01–09 — it's a
separate, later track, and shouldn't be over-specified before Focus 1/2
land and inform what's actually available to build on. Revisit and expand
this file's substeps once Steps 01–09 are further along.)*

1. **Done (2026-07-31).** Re-read `vinu_portfolio/service.py`'s
   `build_portfolio()`, `allocate_risk_parity()`, and
   `compute_correlation_matrix()` in full to confirm the current baseline
   precisely. Found and fixed a real bug while doing this (not just
   documented — see `AGENTS.md`'s Step 10 entry for full detail):
   `build_portfolio()` was passing `compute_correlation_matrix()`'s output
   (a correlation matrix, values bounded [-1, 1], diagonal 1.0) into
   `allocate_risk_parity()`'s `returns_df` parameter, which then computed
   `.std() * sqrt(252)` on it as if it were a daily-returns time series —
   a meaningless quantity, not volatility. Net effect: the "risk-parity"
   (inverse-vol) weighting had never actually weighted by real volatility.
   Fixed by extracting a shared `_build_returns_df()` helper so
   `build_portfolio()` now passes actual returns to the allocator and
   derives the correlation matrix from the same fetch. Zero tests existed
   for any of these three methods before this — added
   `vinu-portfolio/tests/test_service.py` (10 tests, including a
   regression test that fails against the old buggy wiring). **The
   corrected baseline**, confirmed by direct re-read: `build_portfolio()`
   is still a same-day, stateless pipeline — no regime-awareness, no
   memory of prior days' outcomes, no probability model. That part of the
   original framing was accurate; only the vol calculation itself was
   broken. Substeps 2–4 below should design against this now-correct
   baseline, not the broken one.
2. **Done (2026-07-31).** Regime-read design + build. Of the 11 angles,
   only `regime_analysis` is a true regime classifier — but its *stored*
   output is a window-aggregate (per-regime win rate/Sharpe/`pct_of_time`
   across the whole analyzed history), not a "today's regime" scalar.
   Built `vinu_portfolio/regime.py::classify_current_regime()`, a
   documented reimplementation of that angle's own `classify_regime()`
   thresholding applied to just the latest benchmark-symbol observation,
   rather than trying to extract a current-state value the angle's stored
   shape doesn't contain. Full reasoning in
   `project-understanding/skills/daily-allocation/SKILL.md`.
3. **Done (2026-07-31).** Outcome-memory design + build. Reused
   `vinu-research`'s existing `calibration_entries` table (already wired
   end-to-end from `vinu-live`'s feedback loop) rather than adding new
   storage — added the one missing piece, a read route
   (`GET /research/trade-plan/{artifact_id}/calibration`). Real, documented
   limitation: only `type == "trade_plan"` artifacts get entries; YAML
   strategies have zero outcome tracking anywhere in the codebase and are
   explicitly reported "not_tracked," never guessed.
4. **Done (2026-07-31), as a v1.** Probability-weighting model:
   `PortfolioService.compute_daily_allocation()` applies two bounded
   multiplicative tilts (regime alignment via `tags.yaml`, outcome
   confidence via calibration accuracy) to the existing risk-parity base
   weight, then renormalizes. Explicitly a defensible first cut, not a
   solved research problem — see the skill doc for the tags.yaml/
   regime_analysis vocabulary mismatch this had to resolve, and for how
   this only partially compensates for Stage 2 (`ShadowEvaluator`) never
   running. Also wired `sizing.py`'s previously-dead
   `apply_position_sizing()` in as the final step (weights → $ position
   sizes), gated on live equity being available.
5. **Not started — deliberately.** This is a human/design checkpoint, not
   something a single pass can self-certify. Exposed as
   `GET /portfolio/daily-allocation` + `vinu-portfolio daily-allocation`
   CLI, **on-demand only** — not added to `entrypoint.sh`, mirroring
   `promote_scan_main`'s "consequential action stays manually invoked"
   precedent. No path to real capital exists yet; wiring this into
   anything that moves money is explicitly out of scope until this
   checkpoint happens on purpose.

## Open risks / assumptions

- This step's scope is the least concretely defined in the whole plan —
  treat the substeps above as a starting scaffold, not a final list.

## Definition of done

*(To be refined once this step is actually started — premature to define
precisely before the design substeps above have been worked through.)*
- [x] Baseline (`build_portfolio()` as it exists today) re-confirmed —
      and a real vol-calculation bug found and fixed in the process
      (2026-07-31), with regression test coverage added.
- [x] Regime-read, outcome-memory, and probability-model each have their
      own resolved design, not just a bullet point here — and real,
      tested code (2026-07-31): `vinu_portfolio/regime.py`,
      `PortfolioService.compute_daily_allocation()`, new calibration read
      route in `vinu-research`, `daily-allocation/SKILL.md`.
- [ ] Reviewed against Step 09's safety doc before any live wiring
      (substep 5 — deliberately not started; on-demand only, no scheduler,
      no capital path yet).
