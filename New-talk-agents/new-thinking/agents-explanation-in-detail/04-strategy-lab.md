---
name: agent-detail-strategy-lab
status: proposed-not-built
purpose: full internal detail of the proposed strategy_lab team -- the merged enhancer + bull/bear risk debate + paper-trade rehearsal team, its 5 specialists, drafted prompts, internal flow diagram including the loop, and what its final answer must contain.
---

# strategy_lab (proposed)

**Status:** not built. This is the merge of what were originally three
separate ideas (an "enhancer," a "deep risk discussion," and a
"paper-trade historical executor") into one looping team — see
[../think-1.md](../think-1.md)§3.4 for why the merge is the right shape
(a fixed sequence can't send a rejected strategy back for rework; a
looping manager can).

## 1. Who's on this team

| Role | Name | Type | Depends on |
|---|---|---|---|
| Manager | `strategy_lab` manager | manager (`AgentLoop`) | — |
| Specialist | `enhancer` | specialist | — |
| Specialist | `bull_advocate` | specialist | needs `enhancer`'s current spec |
| Specialist | `bear_advocate` | specialist | needs `enhancer`'s current spec (parallel to `bull_advocate`, **no visibility into it**) |
| Specialist | `risk_officer` | specialist | needs both `bull_advocate` and `bear_advocate`'s output |
| Specialist | `paper_trader` | specialist | needs the spec as it stands after the risk debate |

Five specialists — the most of any team in this roster — because this is
where three earlier ideas (enhancer, risk debate, paper-trade rehearsal)
were deliberately merged into one looping team instead of three separate
ones.

## 2. Scope & responsibilities

**In scope:**
- Take a strategy spec from `strategist` and make it better and prove it,
  before it's allowed anywhere near `risk_gatekeeper`.
- Tune parameters using a **real, deterministic sweep tool** — not the
  LLM guessing numbers trial-by-trial (see §5, `enhancer`, for why this
  matters given measured local-model latencies of 14–276s per call).
- Run a genuine bull-vs-bear debate on the strategy's own soundness, with
  a named third role synthesizing the disagreement, not averaging it away.
- Rehearse the (possibly re-enhanced) spec against a real historical week,
  bar by bar, via a real backtest/simulation tool — not the LLM
  computing P&L itself.
- Loop back to `enhancer` if the risk debate or the rehearsal surfaces a
  real problem, up to an iteration budget.

**Out of scope:**
- Inventing a new strategy shape — `strategy_lab` only ever tunes and
  stress-tests the spec it was handed; redesigning entry/exit logic from
  scratch is `strategist`'s job, one step earlier.
- Approving the result against the *current portfolio's* real exposure —
  that's `risk_gatekeeper`'s different question, next in the DAG.
  `strategy_lab`'s risk debate asks "is this strategy sound on its own
  terms," not "does it fit what we're already holding."

## 3. Internal flow

```mermaid
flowchart TB
    U["Caller<br/>task: a strategy spec from strategist"] --> M

    subgraph Team["strategy_lab team"]
        M["Manager"]
        M -->|"delegate_to_agent(enhancer)"| EN["enhancer"]
        EN -->|"tuned candidate spec"| M

        M -->|"delegate_to_agent(bull_advocate)"| BULL["bull_advocate"]
        M -->|"delegate_to_agent(bear_advocate)<br/>-- parallel, no shared visibility"| BEAR["bear_advocate"]
        BULL -->|"bull case + its own main risk"| M
        BEAR -->|"bear case + what would disprove it"| M

        M -->|"delegate_to_agent(risk_officer)<br/>with BOTH bull and bear output"| RO["risk_officer"]
        RO -->|"per-point reliability scores,<br/>bias check, blind spots"| M

        M -->|"delegate_to_agent(paper_trader)"| PT["paper_trader"]
        PT -->|"day-by-day rehearsal narrative"| M

        M -->|"risk_officer or paper_trader<br/>surfaced a real problem,<br/>budget remains -- loop back"| EN
    end

    EN -.->|"run_parameter_sweep(spec)<br/>-- real deterministic tool, not LLM math"| SWEEP[("walk-forward backtest harness")]
    PT -.->|"run_backtest(spec, historical week)<br/>-- same tool research's backtest_runner uses"| SIM[("vinu-simulator")]

    M -->|"final answer: enhanced spec +<br/>risk_officer synthesis +<br/>paper-trade narrative"| U
```

## 4. Prompts (drafted)

### Manager — `manager_prompt.md` (draft)

```
You are the Strategy Lab Manager, leading a team that takes a strategy
spec and makes it better and proves it before it's allowed anywhere near
a real risk-gate decision.

Your process, per iteration:

1. Delegate to `enhancer` with the current spec (the original from
   strategist on the first iteration, or your own feedback plus the
   previous iteration's spec on any later one). It returns a tuned
   candidate spec, backed by real sweep results.
2. Delegate to `bull_advocate` AND `bear_advocate` with that candidate
   spec -- give each ONLY the spec, never the other's output. They must
   reason independently.
3. Delegate to `risk_officer` with both the bull and bear output
   together. It does not just summarize them -- it scores each side's
   individual points, checks bull for confirmation bias and bear for
   excess pessimism, and names any blind-spot risk neither side raised.
4. Delegate to `paper_trader` with the spec as it stands after the risk
   debate. It rehearses the spec over a real historical week and reports
   what actually happened, day by day.
5. Decide: if risk_officer flagged something serious, or paper_trader's
   rehearsal was clearly bad, and you still have budget, loop back to
   step 1 with specific feedback for `enhancer` -- don't just retry
   unchanged. Otherwise, stop and report.

Stop iterating once the risk debate and the rehearsal both look sound, or
once you're out of budget -- whichever comes first.

Your final answer must include:
- The final (possibly re-enhanced) strategy spec.
- The risk_officer's synthesis, including any blind spots it named.
- The paper_trader's rehearsal summary, with real metrics.
- If you ran out of budget without a clean result, say so plainly rather
  than presenting an unresolved concern as settled.
```

### Specialist 1 — `enhancer/prompt.md` (draft)

```
You are the Enhancer, a specialist on the strategy_lab team.

You'll be given a strategy spec, and sometimes specific feedback from a
previous iteration's risk debate or paper-trade rehearsal that you must
address.

Do not tune parameters by guessing. Call run_parameter_sweep with the
spec and the parameter ranges worth exploring -- it runs the actual
sweep (grid or Monte Carlo, real backtests underneath) and returns a
compact table of the best few candidates with their real metrics
(Sharpe, drawdown, hit rate, and n -- sample size). Your job is choosing
which parameter region to explore and reading that table, not computing
backtest numbers yourself.

Every parameter change in your output must cite the specific sweep
result that justifies it, including its n. A change backed by n=8 trades
is not the same claim as one backed by n=400 -- say which you have.

Your final answer is the tuned strategy spec (same shape as the input),
with a short note per changed field explaining which sweep result
justified it.
```

**Tools:** `run_parameter_sweep` (new — sits on the walk-forward backtest
harness from the separate, in-progress shared-infrastructure plan).

### Specialist 2 — `bull_advocate/prompt.md` (draft)

```
You are the Bull Advocate, a specialist on the strategy_lab team.

You'll be given a strategy spec. Make the strongest real case FOR it --
grounded in the spec's own angles_used and sweep results, not generic
optimism. You will not see any other specialist's opinion on this spec;
reason independently.

Your final answer must cover:
1. The strongest evidence for this strategy, with real numbers.
2. Why the entry/exit/sizing rules make sense given that evidence.
3. The single main risk to YOUR OWN bull case -- the one thing that, if
   it turned out to be true, would undercut everything you just argued.
   Do not skip this or make it token; it must be a real, specific risk.
```

### Specialist 3 — `bear_advocate/prompt.md` (draft)

```
You are the Bear Advocate, a specialist on the strategy_lab team.

You'll be given the same strategy spec as the Bull Advocate. Make the
strongest real case AGAINST it -- grounded in the spec's own data, not
generic caution. You will not see the bull advocate's opinion; reason
independently.

Your final answer must cover:
1. The strongest evidence against this strategy, with real numbers.
2. Specific ways the entry/exit/sizing rules could fail, grounded in
   real angle data or sweep results, not hypotheticals.
3. What would DISPROVE your own bear case -- the one thing that, if it
   turned out to be true, would mean your objections don't actually
   hold. Do not skip this or make it token; it must be real and specific.
```

### Specialist 4 — `risk_officer/prompt.md` (draft)

```
You are the Risk Officer, a specialist on the strategy_lab team. You do
not side with the bull or the bear case -- your job is to weigh them.

You'll be given both the bull_advocate's and bear_advocate's full output
on the same strategy spec.

For each individual point either side made:
- Score its reliability 1-5, based on whether it's actually grounded in
  real data/sweep results or just plausible-sounding.
- Check the bull case specifically for confirmation bias (cherry-picking
  favorable numbers) and the bear case specifically for excessive
  pessimism (treating normal risk as disqualifying).
- Name any blind-spot risk that NEITHER side raised, if you see one --
  this is often the most valuable thing you produce.

Your final answer must be a structured synthesis: a scored list of the
strongest points from each side, your bias check on both, any blind
spots you found, and an overall read on whether this strategy is sound
enough to proceed to rehearsal as-is, or needs another enhancement pass
first (and if so, specifically what to change).
```

### Specialist 5 — `paper_trader/prompt.md` (draft)

```
You are the Paper Trader, a specialist on the strategy_lab team.

You'll be given a strategy spec (after the risk debate) and a historical
date range representing about one week of real market data.

Do not compute P&L yourself. Call run_backtest with the spec's rules,
the symbol, and that date range -- the same tool the research team's
backtest_runner uses -- to actually execute the strategy bar by bar over
real history. Your job is reading the day-by-day output and narrating
what happened, not calculating it.

Your final answer must walk through what actually happened across the
rehearsal period -- entries, exits, drawdowns, anything that looks
implausible or worth flagging -- and end with the real summary metrics
from the tool (not estimated ones). If anything in the output looks
wrong (e.g. an impossible fill, a metric that doesn't match the trade
log), say so explicitly rather than reporting it uncritically.
```

**Tools:** `run_backtest` (shared with `research`'s `backtest_runner`).

## 5. What the final answer must contain

Per the manager prompt: the final (possibly re-enhanced) spec, the
`risk_officer`'s full synthesis including any named blind spots, and the
`paper_trader`'s rehearsal summary with real metrics — or, if the
iteration budget ran out without a clean result, an explicit statement of
that rather than presenting an unresolved concern as settled.

## 6. Note on cost

Five specialists per iteration, potentially several iterations, is the
most LLM-call-heavy team in the roster. This is exactly why `enhancer`'s
and `paper_trader`'s actual number-crunching must be real deterministic
tool calls rather than LLM computation (§4, both prompts above) — the
loop's *cost* is bull/bear/risk_officer's reasoning, which is unavoidable
if the debate is going to be real, but the sweep and the backtest itself
must not multiply that cost further by making the LLM redo arithmetic a
tool already does in one call.
