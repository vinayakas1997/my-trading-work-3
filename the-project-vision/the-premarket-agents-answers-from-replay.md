---
name: the-premarket-agents-answers-from-replay
status: answered-via-1-month-replay
purpose: evidence-based answers to the "can answer" subset of the-premarket-agents-questions.md, sourced from a real (simulated) 20-trading-day agentic replay — 2026-07-06 to 2026-07-31, AAPL/TSLA/JNJ, run-2026-07-06-2026-07-31-v2 — not live trading, and not speculation.
---

# Premarket-Readiness Questions — Answered From the 1-Month Replay

**Source:** `the-1-month-back-testing/results/run-2026-07-06-2026-07-31-v2/`
(`thinking.json`/`response.json`/`account_snapshot.json` per day) and
`report.md`. Every day's transcript was read in chronological order, not
sampled. This replay used the local `qwen3-35B` model through the real
`vinu-agent` HTTP loop, one simulated session reused across the whole
month, `_as_of` clamped per day (item 1's lookahead guard) and fills
executed T+1 by `HistoricalFillBroker` (item 2) — see
`the-1-month-back-testing/full-plan.md` for the full design.

**Read this before the answers below:** two real bugs were found reading
these transcripts that materially limit what this replay can honestly
claim (full detail in `testing-status/day-stepper-replay-harness/test-log
.md` Bug-5 and `testing-status/historical-fill-broker/test-log.md` Bug-2):

1. **The broker never marks a held position to the current price** — only
   at the moment of a fill. AAPL was bought once (2026-07-08, filled
   2026-07-09) and held the rest of the month; every day after that, the
   agent's own `get_portfolio` tool (on the one day it was actually called)
   returned the same frozen entry-day price, not the real, moving one.
2. **The agent stopped calling any tool at all after day 3**, for 16 of the
   remaining 17 days (one exception: 2026-07-13, one `get_portfolio` call).
   It answered every one of those days directly from memory of its own
   prior turns, most likely because the reused session's growing history
   left less completion-token budget each day (`max_tokens=4096` vs. the
   configured `8000`, a known, previously-deprioritized issue — see
   `the-1-month-back-testing/FIXES-2026-08-03.md`).

Together, these mean roughly 16 of 20 simulated days produced no genuine
re-evaluation — the agent was, in effect, asleep at the desk with a stale
newspaper in hand. This is itself a finding (see Section 6 below), not just
a caveat to bury — it directly bears on Section 6's "does the agent
actually monitor an open position unattended" question.

---

## Section 1 — Signal & Strategy Validity

**Does the agent's stated reasoning lean on `significance_score`/sentiment
for direction?**
No instance found across all 20 days. The one real trade decision
(2026-07-08) was built entirely on price/SMA20/RSI14 — legitimate
technical-analysis inputs, not the proven-negative sentiment/
`significance_score` mechanism the plan flags. Direct quote, day 07-08:
*"Strong technical setup with price above SMA20 — Neutral RSI suggests
room for upside — Good recovery from recent lows — Clear trend
confirmation."* `get_news` was never called on any of the 3 tickers during
the entire replay, so sentiment/news signals played no role at all in this
run — not because the agent avoided them on principle, but because the
tool-call dropout (above) meant it never got that far after day 3, and
before that, it prioritized price/technicals over news. Verdict: **clean
on this specific question**, but the absence of `get_news` calls means this
replay doesn't actually exercise the news-driven decision path the
question is really probing — logged as a gap, not a pass.

**Does it treat a low-sample ticker (JNJ, AUC 0.75 on 6 test positives)
with the same confidence as a high-sample one (AAPL/TSLA)?**
Worse than that — **JNJ's price data was fabricated after day 3.** On
2026-07-08, the agent correctly called `get_stock_price`/`get_features` for
JNJ and got a real close of **$267.16** (confirmed against the raw tool
response). Starting the very next simulated day (2026-07-09) — a day with
**zero tool calls** — its "Technical Analysis Update" stated:

> ### JNJ (No Position)
> - **Price**: $162.45 (up from ~$158)
> - **Technical**: Strong uptrend, RSI ~73 (approaching overbought)

$162.45 is not a real JNJ price from any point in this window (nowhere
close to the real $267.16 anchor one day earlier, and JNJ never traded
near $162 in the actual archived data) — nothing in the transcript fetched
it, and no tool result contains that number anywhere in the session. It is
best explained as the model inventing a plausible-looking number under
token pressure, formatted with exactly the same confident, decimal-precise
style as real tool output. That fabricated number then propagated
**verbatim, unquestioned, for 13+ consecutive days** (07-09 through
07-31), presented every time as a "Technical Analysis Update" alongside a
real, stale-but-genuine AAPL number. A reader of these transcripts without
access to the raw tool calls would have no way to tell the fabricated JNJ
line from a real one — this is a materially more serious finding than "low
confidence on a small-sample ticker": **the agent will confidently state a
number it never actually retrieved, indistinguishable in tone from a
number it did.**

---

## Section 3 — Risk Management & Loss Adaptation

**After a losing day/string of losing days, does the agent's reasoning
change?**
Cannot be meaningfully answered from this run, and the reason why is
itself the answer: because of the broker's frozen mark (Bug-2 above), the
agent was **never shown a real loss to adapt to**. Its own tool response
reported a static ~-0.15%/-0.65% "drawdown" for three straight weeks; the
*actual* mark-to-market path (computed after the fact from real historical
closes, see `report.md`) shows the position was unrealized **+$2,925 at
its 2026-07-28 peak** and back to a real loss by month-end — a swing the
agent's own tools never surfaced. Any conclusion about "did it adapt to a
loss" would be answering a question about a loss the agent was never told
it had. What can be said cleanly: on the two days it *did* actually
re-check (07-08 initial entry, 07-13 the one later real `get_portfolio`
call), its stated reasoning stayed internally consistent and did not
change its story to fit new numbers — a mild positive, but a low bar given
how little genuine re-evaluation happened at all.

**Does it reference the graduated risk-budget tiers unprompted?**
No. Across 20 days, zero mentions of `risk_budget.py`'s -1%/-2%/-3% tiers,
or any risk-tier language at all. The agent's own risk framing was purely
qualitative ("the -0.65% drawdown is within normal trading noise") and, per
`the-project-vision/the-premarket-agents-questions.md` Section 3, that
tracks the known, dormant state of the graduated tiers — nothing surprising
here, but now confirmed by direct transcript evidence rather than code
inspection alone.

**Are stop-loss/take-profit brackets actually used?**
No. The one real order (`submit_order({"order_type":"market","qty":100.0,
"side":"buy","symbol":"AAPL"})`) passed no `stop_loss_price` or
`take_profit_price`, despite `AlpacaBroker`/`HistoricalFillBroker` both
supporting them. This is a naked market order with no resting exit — exactly
the risk the original questions doc flagged as a real gap, now confirmed in
an actual decision, not just in the API surface.

---

## Section 6 — Human-in-the-Loop & Governance (partial, as scoped)

**Does the agent's behavior around monitoring/confirmation make sense in
this compressed setting?**
The dominant finding here is the tool-call dropout itself. A human PM who
opened a position, then for the next 16 consecutive sessions never once
re-pulled a price or a portfolio snapshot — instead re-issuing the same
paragraph with a new date stamped on it, at one point inventing a ticker's
price outright — would not be considered to be monitoring the position at
all. This replay makes concrete a governance question the source document
poses abstractly: an unattended agent that silently stops doing its actual
job, while still producing fluent, formatted, confident-sounding daily
output, is a **more dangerous** failure mode than one that visibly errors
out, because nothing in the transcript *announces* the failure — a human
skimming daily summaries would see "Decision: Hold Current Position,
reasoning: [plausible paragraph]" every day and have no signal that no new
information was actually consulted 16 times running.

`require_confirmation` behavior specifically could not be assessed — the
one real order in this replay went through the replay's own historical-fill
path, not a live confirmation flow, and no order in this run was ever
rejected or required human sign-off to observe how the agent would react.

---

## Explicitly out of scope for this replay (per the source doc's own framing)

- **Section 2 (Premarket-Specific Conditions)** — this replay used
  regular-session daily bars (`interval=1D`, decision point 09:30 ET); there
  is no premarket data anywhere in this stack, replayed or otherwise. Nothing
  here should be read as evidence about premarket readiness.
- **Section 4 (Execution & Market Microstructure)** — the historical
  broker's fills used a cost model (Almgren-Chriss), not real market
  microstructure; this replay can speak to whether the *strategy* looked
  reasonable on paper, not what real slippage/rejects would do to it.
- **Section 7 (Promotion Path)** — `ShadowEvaluator` is dormant regardless
  of this replay; this replay is not a substitute for wiring it up, and
  nothing here should be cited as evidence the promotion path is closed.

---

## New bugs this reading surfaced (already logged elsewhere, cross-referenced here per the item's own instructions)

- `testing-status/day-stepper-replay-harness/test-log.md` **Bug-5** — tool-call
  dropout after day 3, likely `max_tokens` starvation from a growing reused
  session.
- `testing-status/historical-fill-broker/test-log.md` **Bug-2** — position
  mark never refreshed outside a fill event; the agent's own tools showed it
  a frozen P&L for three weeks while the real position swung by thousands
  of dollars.
- **Not yet logged anywhere else, logging here:** the fabricated JNJ price
  (`$162.45`, first appears 2026-07-09, repeated through 2026-07-31) is a
  new, distinct finding — not explained by either bug above, since it isn't
  a stale-but-real number, it's a number that never existed in any tool
  response this session. Worth a dedicated investigation (does the model
  hallucinate plausible-sounding numbers under token pressure specifically,
  or is this reproducible outside a replay context too) before trusting
  this model's unattended output in any live setting, premarket or not.
