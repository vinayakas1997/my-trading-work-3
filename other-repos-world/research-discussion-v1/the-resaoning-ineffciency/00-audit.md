# The "absolute number" audit — every self-admitted un-tuned threshold in the system

Triggered by the 2026-09-11 "would you put real money on this" conversation
(`complete-plan/05-progress-log.md`'s matching entries). The honest answer
was no, and the #1 reason given was: several numbers that directly govern
risk and money were picked by *reasoning about what sounds right*, not by
*measuring what actually works*, and several of them literally say so in
their own code comments ("Provisional, not tuned — same 'flag it, don't
pretend it's settled' discipline...").

This file is the full list, found by grepping the whole codebase for that
admission (and its synonyms — "first-pass", "unvalidated", "arbitrary"),
not by guessing where they might be. Every one is categorized by how much
it actually matters and what fixing it actually requires — because not all
of these are the same problem, and treating them as if they were would
mean either wasting effort re-deriving something already well-reasoned, or
"fixing" a number that can only really be fixed by watching real (or
paper) trades happen.

## How to read this list

- **A — Already reasoned, not actually a problem.** Has a citation, a
  convention it matches, or an explicit "why this exact number" — just
  wasn't obvious from the earlier "would you trust this" conversation
  because these hadn't been separated out from the real Category C list
  yet. No action needed; listed here so the full picture is honest, not
  cherry-picked to look better than it is.
- **B — Operational cadence, not a risk number.** Controls how often a
  worker runs / how much it costs to run, not how much money is put at
  risk on a single decision. Getting it wrong means stale data or wasted
  LLM spend, not a bad trade. Lower priority.
- **C — A real risk/decision threshold, genuinely unvalidated.** Sits
  directly between a signal and money or a promotion decision, and the
  number was picked by judgment, not evidence. These are the ones the
  "would you trust it" verdict was actually about.
  - **C1 (fixable now)**: can be replaced with better-reasoned logic
    using data the system *already computes* — no need to wait for real
    trading history.
  - **C2 (needs real data)**: can only be honestly calibrated by watching
    real or paper trades accumulate. Flagged with a concrete trigger
    condition instead of a guessed replacement number.

---

## Category A — already reasoned, confirmed correct as-is

| # | Constant | Value | Where | Why it's actually fine |
|---|---|---|---|---|
| A1 | `promotion_deflated_sharpe_threshold` | 0.95 | `vinu-research/vinu_research/config.py:126` | The standard multiple-testing-corrected significance level (Bailey & López de Prado 2014) — cited, not guessed. |
| A2 | `promotion_pbo_threshold` | 0.7 | `vinu-research/vinu_research/config.py:136` | Matches `sweep_grid.py`'s existing `pbo_severe` convention — an internal consistency choice, not an isolated guess. |
| A3 | `stress_test_max_drawdown_threshold` | -0.50 | `vinu-research/vinu_research/config.py:157` | Explicitly reasoned as deliberately lenient — "crisis windows are *expected* to hurt, this is meant to catch catastrophic/leveraged blowups, not ordinary drawdown." |
| A4 | `kelly_fraction` | 0.25 | `vinu-agent/vinu_agent/agent/position_sizing.py:38` | Cited to a reference doc recommending 25–50% of full Kelly; sits at the conservative end on purpose. |
| A5 | `risk_per_trade_pct` | 0.02 | `vinu-agent/vinu_agent/agent/position_sizing.py:44` | The standard "1–2% rule" fixed-fractional convention, named as such in the comment. |
| A6 | `atr_stop_multiple` | 2.0 | `vinu-agent/vinu_agent/agent/position_sizing.py:46` | Standard 2×ATR stop convention, cited. |
| A7 | Catastrophic-backstop stop distance | derived, not fixed | `vinu-live/vinu_live/trade_plan/orchestrator.py:1058` | Computed from the plan's own real `cvar_95_limit` estimate, not an invented flat distance — the code explicitly chose this over a guessed number for this reason. |

**No action taken on these.** Listed for completeness, not as work items.

---

## Category B — operational cadence (real, but not a risk-of-loss number)

| # | Constant | Value | Where | What it actually controls |
|---|---|---|---|---|
| B1 | `planner_worker_interval_sec` | 1800 | `vinu-agent/vinu_agent/config.py:63` | How often the LLM screener+research cycle runs. Too slow = stale ideas; too fast = LLM cost. |
| B2 | `capital_allocator_worker_interval_sec` | 900 | `vinu-agent/vinu_agent/config.py:106` | How often approved-but-unfunded candidates get a funding pass. |
| B3 | `risk_gatekeeper_worker_interval_sec` | 900 | `vinu-agent/vinu_agent/config.py:97` | How often a PASS'd research run gets sized and gated. |
| B4 | `skill_audit_worker_interval_sec` | 3600 | `vinu-agent/vinu_agent/config.py:59` | How often skill-file edits are re-checked. |
| B5 | `significance_worker_interval_sec` | 900 | `vinu-agent/vinu_agent/config.py:88` | How often the significance-triage notifier scans for patterns worth flagging. |
| B6 | `summary_parallelism` | 3 | `vinu-agent/vinu_agent/config.py:71` | Per-ticker LLM call concurrency, bounded by free-tier rate limits. |
| B7 | `_SHOCK_DEBOUNCE_SEC` | 60.0 | `vinu-live/vinu_live/trade_plan/orchestrator.py:602` | Minimum gap between off-cycle shock-triggered re-evaluations for the same symbol. |
| B8 | `capital_allocator_budget` | 100000.0 | `vinu-agent/vinu_agent/config.py:114` | Explicitly a **placeholder**, not a guess — "pending a real funding-capital source (broker buying power)." Different category from the rest: known-incomplete, not un-tuned. |

**Recommendation: leave as-is for now.** Getting one of these wrong costs latency or LLM spend, not a bad trade. Revisit only if a real operational pain point shows up (e.g. ideas going stale, LLM budget blowing out) — don't tune blind.

---

## Category C — real risk/decision thresholds, genuinely unvalidated

| # | Constant | Value | Where | What it decides |
|---|---|---|---|---|
| C1a | `_REBALANCE_PROTECT_GAIN_PCT` | 0.05 (flat) | `vinu-live/vinu_live/trade_plan/orchestrator.py` | Whether a real open position with an unrealized gain is protected from being unwound to satisfy a portfolio rebalance request. **Directly decides whether a real winning position gets closed.** |
| C1c | Bracket 1R take-fraction | 0.5 (flat) | `vinu-live/vinu_live/trade_plan/orchestrator.py` | How much of a position gets sold once it hits 1R gain. Found while writing `test_pre_live_scenarios.py`'s trailing-stop scenario, not in the original grep sweep — a flat 50% fired mid-rally regardless of how far past 1R the move already was. |
| C1b | `NEAR_DUPLICATE_THRESHOLD` | 0.5 | `vinu-agent/vinu_agent/agent/thesis_intake_gate.py:19` | Whether a new trade idea is similar enough to an existing one to be treated as a duplicate (and dropped before it ever reaches an LLM call). |
| C2a | `K_CAP_DEFAULT` | 3 | `vinu-agent/vinu_agent/agent/thesis_intake_gate.py:21` | Max new candidate ideas allowed through per cycle. |
| C2b | `DEFAULT_MAGNITUDE_TOLERANCE` | 0.15 | `vinu-agent/vinu_agent/agent/angle_consensus.py:26` | How much two independent forecasting "angles" can disagree in predicted magnitude and still count as "agreeing" — feeds a confidence/consensus signal. |
| C2c | `REJECTED_PATTERN_MIN_COUNT` / `_WINDOW_HOURS` | 3 / 24.0 | `vinu-agent/vinu_agent/agent/significance_triage.py:49-52` | When a pattern of rejected proposals is flagged to a human as worth attention. |
| C2d | `LARGE_FUNDING_WINDOW_HOURS` | 24.0 | same file | Window for detecting a burst of large funding events worth flagging. |
| C2e | `THESIS_CONTRADICTION_WINDOW_HOURS` / `_MIN_COUNT` | 24.0 / 1 | same file | When a thesis contradiction is flagged. |
| C2f | `borrow_cost_annual` | 0.0075 (flat, all symbols) | `vinu-simulator/vinu_simulator/engine/costs.py:17` | The short-borrow cost charged in backtests — affects which strategies look profitable enough to promote. Explicitly documented as "not calibrated per symbol." |
| C2g | `completeness_tolerance` | 0.95 | `vinu-research/vinu_research/sweep_grid.py:283` | Whether a parameter-sweep grid is complete enough to trust its results. |

### C1a — fixed now: `_REBALANCE_PROTECT_GAIN_PCT` (vinu-live)

**The problem with the flat 5%:** a 5% unrealized gain means something
completely different for a low-volatility name (a real, hard-won move) and
a high-volatility name (routine daily noise). A flat percentage protects
noise-driven "gains" on volatile names just as readily as it protects a
genuine move on a calm one — the exact "arbitrary, not connected to what
the number is supposed to represent" gap this whole audit is about.

**The fix:** scale the protection threshold by the position's own realized
volatility instead of a flat percent — data the orchestrator already
computes every cycle (`_fetch_recent_prices` → `_simple_returns`, already
used for the trailing-stop ATR calc). A gain has to be several real
volatility-units in size to count as "worth protecting," not just an
arbitrary 5%, on ANY symbol. This needed no new live trading history — the
volatility data was already being computed and discarded.

*(Implemented separately — see the matching entry in
`complete-plan/05-progress-log.md`.)*

### C1c — fixed now: bracket 1R take-fraction (vinu-live)

**The problem with the flat 50%:** found only while writing the pre-live
mechanical scenario test, not in the original grep sweep — a rising-price
scenario expected a plain `hold` at every bar and instead got
`bracket_partial` mid-sequence, because the flat 50% partial-take fires the
instant price crosses 1R, taking the same half-the-position bite whether
the move is *just* at 1R or has already run to 4R or 6R past it.

**The fix, same idiom as C1a**: the take-fraction now scales with the
R-multiple actually achieved (`_gain / _risk`, which this function already
computes) — 1R takes 25%, 2R takes 50%, capped at 75% so the mechanism can
never fully close a genuine runner on its own (the trailing stop /
invalidation rules remain responsible for that). Confirmed against how
other repos handle exactly this instead of inventing the pattern from
scratch: `comprison-other-vinu/07-abu.md` — `abupy/BetaBu/ABuAtrPosition.py`
scales position size inversely by ATR rather than shipping one fixed
number; `comprison-other-vinu/06-hummingbot.md` —
`TripleBarrierConfig.new_instance_with_volatility_adjustment()` rescales a
position's stop/target/trailing barriers by realized volatility for the
same reason. Both repos treat "one fixed number regardless of how the
position is actually behaving" as the thing to avoid — this fix follows
that same, already-battle-tested pattern.

*(Implemented separately — see the matching entry in
`complete-plan/05-progress-log.md`.)*

### Calibration observation log — started, not a fix by itself

Per the user's own framing: these Category C checkpoints ARE the places in
the system that need to be *observed*, not guessed at further. New
`vinu-infra/calibration_log.py` — a plain append-only JSONL log, gated to
only write once a real broker account is confirmed configured (never for a
synthetic/test run), wired into the `rebalance_protect` and
`bracket_partial` checkpoints so far (the two already touched in this
pass). This does not calibrate anything by itself — it starts the clock on
collecting the real data every other Category C item (C1b, C2a–C2g) is
still waiting on. Extending it to the remaining `vinu-agent` checkpoints
(thesis-dedup, angle-consensus tolerance, significance-triage windows) is
the natural next step, not yet done.

### C1b, C2a–C2g — flagged, not fixed: need real data, not better guessing

Every one of these is a genuine judgment call that can only be honestly
replaced by *measuring* — not by reasoning harder about what number sounds
right. Repricing them without data would just swap one guess for another,
more confident-sounding one. Each gets a concrete trigger instead of a
number:

- **C1b, C2b (similarity/tolerance thresholds)**: calibrate once a
  labeled sample of real thesis pairs / angle-pair outcomes exists —
  i.e. once the system has been generating real ideas for long enough
  that "was this actually a duplicate / did these two angles actually
  agree" can be checked against what happened, not guessed.
- **C2a (K_CAP_DEFAULT)**: this one is closer to a cost-policy decision
  than a statistical unknown — revisit once real LLM spend and candidate
  volume from `planner_worker_interval_sec` running live shows whether 3
  is too tight or too loose, not by re-deriving it on paper.
- **C2c/C2d/C2e (significance-triage windows/counts)**: calibrate once a
  real distribution of rejected proposals, funding events, and thesis
  contradictions exists to check what count/window actually separates
  "noise" from "worth a human's attention."
- **C2f (borrow cost)**: already reasoned as "far closer to reality than
  the implicit zero it replaced" — lower priority; revisit only if
  short-heavy strategies become a real part of the live book, where a
  flat rate would start to matter more.
- **C2g (completeness_tolerance)**: a standard QC bar (95%), not a live
  risk number — no action needed unless real sweep runs start getting
  rejected who shouldn't be.

**None of these are safe to "fix" by picking a different number out of
reasoning alone — that would just be trading one unvalidated guess for
another.** The honest fix is watching the system operate and checking each
one against what actually happened, which is also, not coincidentally,
exactly why "no live track record" (finding #3 from the same conversation)
has to come before "put real money on it" regardless of how many of these
get touched.
