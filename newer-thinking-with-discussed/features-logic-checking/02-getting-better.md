# How does the system get better and better?

Vision: *"learning closed-loop: hypotheses versioned, evidence unified, degradations detected, thresholds recalibrated, syntheses consumed"* (`../vision-trding-system.md` A12, A16, B9, Part C). A learning loop only counts if **three** things are true: something **writes** the result of what happened, something **reads** it, and the read **changes a later decision**. A store that nobody writes, or a metric nobody reads, is not a loop, however good its unit tests are. Each loop below was traced for all three.

**What Phase 1 can prove:** the loop is wired end to end and does the right thing with hand-made numbers. **What it cannot prove:** that the system actually improves. That needs real trades (Phase 2/3). Every answer says which.

---

## Q1. Which loops exist, and is each one fed?

| # | Loop | Writes → stores → reads → changes | Verdict |
|---|---|---|---|
| L1 | **Signal evidence** (what happened after this must-condition fired) | live poller / `signal_evidence` angle → `SignalEvidenceStore` → deciding agent (`get_signal_evidence`), uncertainty score → EXECUTE / SKIP and "how sure" | **FIXED** (F4). Live triggers were recorded with no outcome and nothing ever resolved them. Now resolved after 20 closed bars. See Q2 |
| L2 | **TradeScore calibration** (which sub-score actually predicted winning trades) | closed trade-plan positions → `record_realized_outcome` → calibration history → `propose_calibrated_thresholds` → next plan's score weights | **WORKS** for the trade-plan path (Q3). Not fed by live-decision trades (D3) |
| L3 | **Strategy decay** (is an approved strategy still working) | re-validation Sharpe → bench history → `decay_scan` → status → portfolio drops it | **FIXED** (F1, F2). Was starved. Speed is **DECISION D1** |
| L4 | **Hypothesis evidence** (what was learned about an idea) | signal-evidence summary → `HypothesisRegistry` evidence trail → next idea prompt shows the last 3 | **WORKS, WITH A LIMIT:** connection verified by the routing work; evidence-trail only, no auto-promotion by design |
| L5 | **Candidate graveyard** (what was tried and failed) | generation drafts + sweep losers + rejected hypotheses → read-time union → idea generator avoids repeats | **WORKS, WITH A LIMIT:** informational; not a blocking gate (deliberately open) |
| L6 | **Maturity tier** (how much to trust the whole system) | closed trades with calibration entries + paper days → tier → scales capital, risk limits, prompt language | **WORKS, WITH A LIMIT:** advances only from the trade-plan path (D3) |
| L7 | **Reflection brain** (24 analysts → beliefs → one hourly synthesis → idea generator) | analysts read audit logs, calibration, coverage → `reflection_beliefs` → synthesis → `get_reflection_synthesis` | **WORKS, WITH A LIMIT:** wired and instrumented (routing work); its analytical quality was not logic-checked here and needs data |
| L8 | **Loss attribution** (which trade-score tier is losing more than before) | audit rows → `loss_attribution` → belief | **WORKS** for trade-plan trades only (D2) |

---

## Q2. L1 in detail: does the live-decision loop learn from what happened after a signal?

**Verdict: FIXED (F4).**

The deciding agent is told things like "this condition fired 34 times, 58% were positive afterwards". That needs, for each past firing, the forward outcome.

**What I found:** two writers feed the evidence store. (a) The historical `signal_evidence` angle computes outcomes, but for exactly one hard-coded condition (`sma5_cross_sma50`). (b) The live poller records each real firing of a strategy's *own* must-condition, with the outcome **empty**, and nothing in the codebase ever filled it in: the store's own docstring says *"whatever job ends up computing outcomes (not built yet)"*, and `get_unresolved_triggers` had no caller. So for any strategy whose condition is not SMA5/50, the evidence the vision relies on ("last-N evidence → decision") had **no outcomes, ever**. A second small defect: the poller did not send the timeframe, so a daily strategy's triggers were stored labelled `15min` (the store's default).

**Fix:** on every new candle the poller resolves the open triggers of that (ticker, timeframe): once 20 closed bars have passed since the trigger bar, it computes the outcome with the same formulas and 20-bar horizon as the angle and posts it (`poller._resolve_signal_outcomes`). Triggers now carry their timeframe. It records the `research.unresolved_triggers->live.poller` connection (with a layer B contract), is on by default (recording only; flag `VINU_LIVE_DECISION_SIGNAL_OUTCOMES_ENABLED`), and never raises.

**Worked example (horizon 20):** a trigger fires on a bar closing `100.0`. Over the next 20 closed bars the highest close is `108.0`, the lowest `97.0`, the last `103.0`.

| Outcome field | By hand | Computed |
|---|---|---|
| best excursion | (108 − 100) / 100 | **+0.08** |
| worst excursion | (97 − 100) / 100 | **−0.03** |
| return at horizon | (103 − 100) / 100 | **+0.03** |

Rules also asserted: with only 19 bars of future the trigger waits; an already-resolved trigger is not posted twice; a trigger of another timeframe or older than the fetched window is left alone; a malformed row is skipped, not fatal; a failed read or post never raises and is recorded as `missing`; a renamed `triggers` key is recorded `malformed`.

Tests: `vinu-live/tests/test_live_decision_signal_outcomes.py` (13; mutation-checked: changing the horizon return makes the by-hand test fail), `vinu-research/tests/test_routes_signal_evidence.py::TestSignalEvidenceListContract` (the real route validates against the contract).

**Waits for data:** how many triggers a real strategy produces per month decides when "34 triggers" exists at all.

**Still open (DECISION D4):** `get_signal_evidence` returns the symbol's triggers for **every** condition mixed together, and the `outcomes_recorded` count that drives the uncertainty score ("no recorded outcomes", +2) is symbol-wide, not specific to the strategy's own must-condition. A strategy with no outcomes of its own can look evidenced because the SMA angle backfilled other rows for the same ticker. Filtering by condition needs a name mapping between the angle's names and the live names; options in `00`.

---

## Q3. L2 in detail: how do the score weights move toward what actually wins?

**Verdict: WORKS (trade-plan path).**

`record_realized_outcome` (research) is called for each closed position that has an artifact; it stores the 4 sub-scores with the realized return. Once there are 30 outcomes, `propose_calibrated_thresholds` nudges the 4 maximum points toward whichever sub-score correlates with winning, never past ±20% of the current value per step, never touching the tier cutoffs, and a negative correlation never gets more weight.

**Worked example.** Defaults confluence 40, EV 35, risk 30, regime-fit 30 (sum 135). Correlations with realized return: confluence 0.6, EV 0.3, risk −0.2 (counted as 0), regime-fit 0.0.

| Sub-score | Target (135 × share) | Clamped to ±20% | Result |
|---|---|---|---|
| confluence | 135 × 2/3 = 90 | 40 × 1.2 | **48** |
| EV | 135 × 1/3 = 45 | 35 × 1.2 | **42** |
| risk | 0 | 30 × 0.8 | **24** |
| regime-fit | 0 | 30 × 0.8 | **24** |

Test: `vinu-research/tests/test_trade_score_calibration.py::test_worked_example_how_the_weights_move_toward_what_predicted_wins` (asserts 48 / 42 / 24 / 24 and untouched cutoffs). The state file is written atomically; a proposal can require human approval (propose mode).

**Why it will not chase noise:** below 30 outcomes the function returns `insufficient_sample` and changes nothing; steps are bounded; weights are never fully refitted. This is the system behaving as the "child" the rules ask for: little evidence, small moves.

**Waits for data:** 30 real closed trade-plan trades per calibration step.

---

## Q4. L6: does the system earn more trust as it proves itself?

**Verdict: WORKS, WITH A LIMIT (D3).**

The maturity tier (`cold_start → paper_only → early_live → mature`) scales deployable capital (cold 0.1, paper 0.25, early 0.5, mature 1.0, opt-in), live risk limits and the agent's prompt weighting. `assess()` counts a "real trade" as one **calibration entry**, and a calibration entry is written only for a closed position linked to a research **artifact**.

The live-decision loop trades **strategy YAMLs, not artifacts**, so none of its trades is ever counted: running only that loop, the tier would stay `cold_start` forever and the capital multiplier would stay at 0.1, however well it trades. It is a limit, not an error (the live-decision path is new), but it means "earns more trust" currently has one road.

**DECISION D3**: how should a closed live-decision trade count toward maturity? Options in `00`. The raw material now exists (F3's `return_pct`).

---

## Q5. How does it avoid "learning" from noise or one lucky trade?

**Verdict: WORKS.** Every loop has a floor and a bound, from the code:

| Mechanism | Floor / bound |
|---|---|
| signal evidence | 70 observations minimum for the angle; 5 samples for the evidence-confidence sizer (`min_sample=5`), Laplace-smoothed |
| TradeScore calibration | 30 outcomes; ±20% per step; propose mode needs a named human approver |
| decay | 2+ bench entries; 3 consecutive bad readings before a status change; `propose` mode needs `approve_decay_action(approver=...)` |
| maturity | `mature` needs 30 trades **and** 2 of 3 regimes |
| reflection brain | gathers only notable/significant beliefs (empty most cycles); one bounded LLM call; failure leaves nothing written; outcomes resolved mechanically, not by a second LLM |
| bucket-table (Layer-4 trust number) | **deliberately not built** until real rows exist: the agent works from raw counts plus a qualitative note |

**Waits for data:** whether these floors are the right size. They are guesses that Phase 2 data corrects.
