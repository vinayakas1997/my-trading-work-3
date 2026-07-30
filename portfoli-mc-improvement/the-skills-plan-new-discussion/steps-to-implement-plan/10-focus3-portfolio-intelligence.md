---
name: 10-focus3-portfolio-intelligence
status: Not Started
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
  allocation logic on top of it.
- **Reuses Step 04's tag/alignment concept** — regime-aware strategy
  selection for the daily allocation is structurally the same problem as
  "find a strategy aligned with this regime," just applied at the
  portfolio level instead of the single-strategy level.

## Substeps

*(This step is intentionally left less detailed than 01–09 — it's a
separate, later track, and shouldn't be over-specified before Focus 1/2
land and inform what's actually available to build on. Revisit and expand
this file's substeps once Steps 01–09 are further along.)*

1. Re-read `vinu_portfolio/service.py`'s `build_portfolio()`,
   `allocate_risk_parity()`, and `compute_correlation_matrix()` in full to
   confirm the current baseline precisely.
2. Design the regime-read step: which of the 11 angles map to "what regime
   are we in," and how the daily process queries them via `AngleRunner`.
3. Design the outcome-memory piece: where "yesterday's actual performance"
   is read from, and how it feeds into today's probability weighting —
   likely needs its own small persistent store, check `ResearchStorage`
   and `vinu_portfolio`'s existing storage first before adding a new one.
4. Design the probability model itself — this is the core research
   question of this step and deserves its own dedicated design pass, not
   a substep bullet.
5. Confirm against Step 09's safety doc before wiring this to anything
   that could move real capital.

## Open risks / assumptions

- This step's scope is the least concretely defined in the whole plan —
  treat the substeps above as a starting scaffold, not a final list.

## Definition of done

*(To be refined once this step is actually started — premature to define
precisely before the design substeps above have been worked through.)*
- [ ] Baseline (`build_portfolio()` as it exists today) re-confirmed.
- [ ] Regime-read, outcome-memory, and probability-model each have their
      own resolved design, not just a bullet point here.
- [ ] Reviewed against Step 09's safety doc before any live wiring.
