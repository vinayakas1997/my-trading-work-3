---
name: e2e-one-month-agent-verification
status: definition-phase
purpose: replaces the thin "run a short session" close-out in 03-strategy-research-and-simulation.md with a real 1-month replay, walked question-by-question against 01-vinu-questions-prompt.md's 8-question daily ritual, per ticker — including the PnL/debrief check that was previously missing entirely.
---

# Step 5 — One-Month Agent Replay, Verified Against the 8-Question Ritual

## Why this replaces the old "one short session" close-out

The original last step in `03` just confirmed the agent could read
freshness/fact blocks. That's necessary but not sufficient — it doesn't
confirm the agent's *actual daily ritual* (`../01-vinu-questions-prompt.md`,
8 questions) gets real answers over a real stretch of trading days, and it
never touched PnL/debrief-on-close at all. This file replaces that step.

**Explicitly deferred, same as `04`**: the real Alpaca live-broker
connection. This replay runs entirely through `HistoricalFillBroker`
(replay mode) — that's what makes Piece 2 (debrief-on-close) and the rest
of this checklist testable without needing a live account or waiting for
real positions to actually close in real time.

## 1. Pick the window and run it

Use the last month of the backfilled range — guaranteed full coverage
(news, stock-price, features, initial-analysis, research, simulator all
confirmed present through `2026-06-30` by `02`-`04`) without needing a
second backfill pass:

```bash
python vinu-agent/scripts/run_month_replay.py \
  --start 2026-06-01 --end 2026-06-30 \
  --api http://localhost:8086/agent \
  --data-root vinu-components/data/agent \
  --run-id e2e-2026-06
```

This drives real `POST /agent/sessions` + `POST /agent/sessions/{id}/messages`
calls one trading day at a time, for however many symbols the replay
harness is configured to cover per day — confirm from its output that all
3 tickers (`AAPL`/`TSLA`/`JNJ`) actually get a turn during the month, not
just whichever one happens to be first.

It's resumable — if it fails partway through, re-run the same command
with the same `--run-id` rather than restarting from day 1.

## 2. Walk the 8 questions, per ticker, against what actually happened

For each ticker, after the replay completes, check each question from
`../01-vinu-questions-prompt.md` against real evidence — not against
whether the transcript *sounds* like it answered the question:

**Q1 — which tickers to focus on today**: **not built, explicitly
punted** (`implementation-plan-from-04/AGENTS.md`'s scope addendum). Do
not expect a real answer to this one; if the transcript answers it anyway,
that's the model narrating from general reasoning, not from a real
mechanism — worth noting, not worth blocking on.

**Q2 — risk management**: check the session's ground-truth/mandate state
was actually injected — search the transcript for the `<ground-truth>`
block and confirm `TradingMandate`/`OrderGuard` state (position limits,
exposure caps) appears as data, not narrative. Cross-check against
`vinu-portfolio`'s `/portfolio/risk/status` (from `04`) for the same day.

**Q3 — ticker history**: query the decision journal directly, don't trust
the transcript's paraphrase of it:
```bash
curl -s "http://localhost:8087/research/hypotheses?symbol=AAPL"
```
Confirm real thesis entries exist with real `created_at`/`updated_at`
timestamps inside the replay window, and that the session's transcript
references specifics that actually match this data (invalidation levels,
thesis text) rather than a plausible-sounding but ungrounded summary.

**Q4 — how did it perform in the last live trades (the PnL question)**:
**this is the check that was missing entirely before this file.** Query
the same route, but for `status=validated` or by inspecting each
hypothesis's `evidence` array for an entry with `metric: "realized_pnl"`:
```bash
curl -s "http://localhost:8087/research/hypotheses?symbol=AAPL" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  [print(h['hypothesis_id'], [e for e in h['evidence'] if e['metric']=='realized_pnl']) \
  for h in d['hypotheses']]"
```
Confirm at least one `realized_pnl` evidence entry was written during the
month for at least one ticker whose position closed during the replay —
this is `vinu_agent/broker/debrief.py`'s `PositionCloseDetector` actually
firing on a real (replay) close event, not just existing as tested code.
If **no** position closed during this specific month for any ticker, that's
a legitimate outcome (nothing to debrief) — but confirm that explicitly
(check `HistoricalFillBroker`'s position history for the month) rather than
silently assuming "no evidence" means "it didn't work."

**Q5 — what should the plan be**: confirm `generate_trade_plan` was
actually called at least once per ticker during the month (check the
transcript's tool-call trace, not just whether a plan-shaped answer
appears in the final text) — this was the tool "confirmed never called
during the entire 1-month replay" the very first time this project ran
this exercise; confirm that specific regression hasn't recurred.

**Q6 — which strategy to apply**: the signal-usage contract (built this
session) means `significance_score`/`regime_feature` output now carries
`proven_for`/`not_proven_for` tags — confirm those tags are visible in
whatever `vinu-initial-analysis` data the trade-plan tool fetched during
the replay (`04`'s verification already confirmed the tags exist on the
angle output; this step confirms the agent's actual trade-plan calls
during the month pulled data that has them). **The full "which strategy"
decision logic on top of those tags is still a known gap** — this question
isn't fully answered by anything built so far, confirm the tags are
present, don't expect a complete answer to the question itself.

**Q7 — prospective fact-check**: search the transcript / audit log for any
`AuditVerdictFail` entries logged with `"stage": "prospective"` (Piece 3):
```bash
grep '"stage": "prospective"' vinu-components/data/agent/trade_audit.log
```
If any trade-plan call during the month had a claim with no matching
fetched data, confirm it was caught here (plan not journaled, warning
block present) rather than silently passed through. If none fired, that's
a legitimate "nothing to catch" outcome — but confirm the audit ran at all
per trade-plan call (it always does, per Piece 3's implementation), not
just that it never triggered.

**Q8 — risk/behavior**: the quantifiable half is the same ground-truth +
mandate check as Q2. The qualitative half (when to defer, when to say "not
enough information") is **explicitly out of scope everywhere in this
project** — confirmed unsolved in all six reference repos, not attempted
here. Don't expect or require a real answer to this half; noting it's
still open is the correct outcome, not a gap in this checklist.

## 3. Cross-check the freshness reader fired at least once

```bash
grep '<freshness-warnings' vinu-components/data/agent/sessions/*.json 2>/dev/null
```
(Or check the session transcript directly via the agent API.) Given the
replay window is the tail end of the backfilled range and `04` already
confirmed `analysis_at` timestamps are fresh as of the backfill, this block
may legitimately never fire during this replay — that's expected, not a
failure. If it's needed to actually exercise this piece, temporarily lower
`FreshnessChecker`'s `STALE_AFTER_DAYS` for one manual test call rather
than waiting for real data to go stale.

## 4. Cross-check the research-digest reader fired at least once

The `03`/`04` runs from earlier in this checklist should be *new* to the
agent as of this replay — confirm at least one session's transcript
contains a `<recent-research>` block:

```bash
grep '<recent-research' vinu-components/data/agent/sessions/*.json 2>/dev/null
```

If it's missing, check two things before assuming it's broken: (1) that
`vinu-research`'s config actually has `llm_enabled: true` (the summary is
gated on this — an empty `summary_text` produces no block, by design, not
a bug), and (2) that this is genuinely the first time this replay's
sessions have queried these symbols' runs — the reader only surfaces a run
once per symbol (state file under
`data/agent/research_digest_state/`), so a second pass through the same
month with the same `--run-id` won't show it again. That's the intended
"one-time notice" behavior, not a regression.

## What to confirm before calling the system verified end to end

- [ ] All 3 tickers got at least one session turn during the replay month
- [ ] Q2/Q8 (quantifiable): ground-truth + mandate state confirmed present
      as data in the transcript for at least one session per ticker
- [ ] Q3: journal entries queried directly and cross-checked against the
      transcript's claims about ticker history
- [ ] **Q4/PnL: at least one `realized_pnl` evidence entry confirmed for a
      real position close during the month, or explicitly confirmed that
      no position closed (both are valid outcomes; an untested claim
      either way is not)**
- [ ] Q5: `generate_trade_plan` confirmed called at least once per ticker
      via the tool-call trace, not inferred from the final answer's tone
- [ ] Q6: signal-usage-contract tags confirmed present in data the
      trade-plan tool actually fetched during the month
- [ ] Q7: prospective fact-check confirmed running per trade-plan call
      (via the audit log), whether or not it ever fired a `Fail`
- [ ] Q1 and Q8's qualitative half confirmed still open, not silently
      assumed solved
- [ ] Research-digest reader confirmed to have surfaced at least one
      `<recent-research>` block for a run that genuinely postdates this
      replay's own state file (not a stale leftover from an earlier test
      pass)

Once every box above is checked, the accurate claim is: **the full data
and decision pipeline works end to end, including the newly-built
consciousness-layer mechanisms, under replay conditions.** The real
Alpaca live-broker path remains the one explicitly deferred piece, per
`04`'s note — that's a separate, later check, not part of what "done"
means here.
