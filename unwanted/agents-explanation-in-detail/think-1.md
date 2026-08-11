---
name: vinu-agent-teams-full-design-synthesis
status: proposed-not-built
purpose: single, self-contained explanation of every vinu-agent team we've designed, why each exists, exactly how it works, the shared mechanisms underneath all of them, and what real reference repos (Vibe-Trading, FinRobot, fincept-terminal) confirmed, refuted, or improved about each idea. Written so someone with no prior context in this conversation can read it top to bottom and understand the whole design.
---

# vinu-agent teams — full design synthesis

This is the complete picture as of this conversation: what teams exist or
are proposed, what each one actually does, how they connect, and the
shared plumbing underneath all of them. Nothing here is built yet except
`screener` and `research` (marked below). Related, more formally structured
per-team files live in
[../differnt-teams-plan/](../differnt-teams-plan/00-overview.md) — this
file is the readable, one-stop version with the reasoning and evidence
included inline, not split across files.

## 1. The starting point: what "team" means here

Every team is a **manager + specialists**, built from the same underlying
primitive vinu-agent already has: an `AgentLoop`, configured differently
per role. A team is defined by plain markdown files (`TEAM.md` for the
manager, `agents/*/AGENT.md` per specialist) — not new Python classes. The
manager gets a tool, `delegate_to_agent`, scoped only to its own team's
specialists. The orchestrator (the one thing a person actually talks to)
gets a tool, `delegate_to_team`, to hand off real multi-step work to any
team. Full mechanism: [../01-orchestrator-and-teams-architecture.md](../01-orchestrator-and-teams-architecture.md).

**This is deliberately not a fixed DAG.** A static graph can't let a
manager decide "I need one more backtest before I'm confident," or let a
risk reviewer send a strategy back for rework. Every team here is a
dynamic loop (delegate, read the result, decide what to do next, repeat
until done or out of budget) — the same shape already proven working in
the `research` team, not a pipeline a scheduler walks with no judgment in
the middle.

## 2. The lifecycle flow (not a DAG — has real feedback loops)

```
research (offline, optional)  ---validated idea--->  strategist
                                                          |
                                                          v
screener  ------(angle read)----------------------> strategist
                                                          |
                                                          v
                                                    strategy_lab
                                              (enhance + risk debate +
                                               paper-trade rehearsal,
                                               loops internally)
                                                          |
                                              <--- reject, back to strategist
                                                          |
                                                     risk_gatekeeper
                                            (portfolio-fit check, real $ next)
                                                          |
                                              <--- reject, back to strategist
                                                          |
                                                   capital_allocator
                                        (decides who actually gets funded,
                                         across ALL approved candidates)
                                                          |
                                                          v
                                          Phase 6 execution (broker, outside
                                                vinu-agent entirely)
                                                          |
                                                          v
                                    trade_monitor  <---->  shadow_ledger
                                  (periodic re-check,      (deterministic,
                                   live position vs         no LLM, runs
                                   its shadow twin)         continuously)
                                                          |
                                                (position closes)
                                                          v
                                                  post_trade_review
                                          (predicted vs. actual, incl.
                                           the shadow twin's full path)
                                                          |
                                                lessons feed back to
                                                          v
                                                     strategist
```

Two real loops exist on purpose: a rejection at `strategy_lab` or
`risk_gatekeeper` sends work back to `strategist`, and every closed trade's
lessons feed the *next* cycle's `strategist` call. That's why this is a
flow with feedback, not a DAG — see the DAG-terminology discussion below
for why that distinction actually matters here.

## 3. The 8 teams

### 1. `screener` — built, real, tested against a live LLM

**Role:** for each symbol in a watchlist, pull together every
vinu-initial-analysis "angle" (currently ~31 separate computed signals per
symbol, most still empty since the underlying service has no historical
data yet) and produce one honest, evidence-grounded read per symbol.

**How it works:** one manager, one specialist (`angle_synthesizer`). The
manager delegates once per ticker. The specialist calls a single tool,
`get_all_angles(ticker)`, which fetches every angle's latest result in one
call. Rule enforced in the specialist's prompt: only treat an angle as
informative if `row_count > 0`; if most/all angles are empty, say so
plainly rather than padding a confident-sounding summary out of nothing.

**Real test result:** ran against a live local LLM (`prism-ml/bonsai-27b`
via LM Studio). All 7 real LLM calls succeeded, both specialist
delegations completed with real content — but the *manager's own final
answer* hallucinated "persistent timeouts" that never actually happened,
despite the real records showing success. This is the exact bug that
motivated the "verify the manager" mechanism below (§4.1) — found by
actually running this team for real, not theorized in advance.

### 2. `research` — built, real

**Role:** offline, exploratory strategy idea generation — not tied to a
specific symbol's current data the way `strategist` is. Generate a
candidate idea, backtest it, risk-critique it, iterate until
`VERDICT: PASS` or `STOP`.

**How it works:** manager + 3 specialists — `idea_generator`,
`backtest_runner` (calls `vinu-simulator`'s `/simulate/custom` directly),
`risk_critic`. Replaces what used to be a separate, always-running
`vinu-research` service — same loop, now just a team.

**Open gap:** doesn't read vinu-initial-analysis angle data at all today —
`idea_generator` isn't grounded in real angle signals the way `strategist`
is. Not yet decided whether that's a bug to fix or the intended point
(pure idea exploration, unconstrained by what data happens to exist).

### 3. `strategist` — proposed

**Role:** take one symbol's angle read (from `screener`, or a validated
idea from `research`) and produce a **concrete, structured strategy spec**
— entry rule, exit rule, stop, position-sizing approach — every field
traceable to a specific angle's real numbers, never invented.

**How it works:** one symbol at a time. Reuses `get_all_angles`. Output is
a structured spec (exact JSON shape not yet pinned down — needs to be
agreed once since `strategy_lab`, `risk_gatekeeper`, and `capital_allocator`
all consume it), minimum fields: `symbol`, `direction`, `entry_condition`,
`exit_condition`, `stop_loss`, `position_size_rule`, `angles_used`,
`angles_missing`.

**Hard rule:** if most angles for a symbol are empty (the real, current
state — vinu-initial-analysis has no data yet as of this writing), the
honest output is "not enough data to propose a strategy yet," never a
confident guess. Same discipline `screener` already enforces.

**Also required (new, from §4.2):** must consult the per-symbol memory
ledger before proposing — what's been tried on this symbol before, what
held up — so every cycle doesn't start from zero.

### 4. `strategy_lab` — proposed (this is a merge of three earlier ideas)

This was originally sketched as three separate teams — an "enhancer," a
"deep risk discussion," and a "paper-trade historical executor." Merging
them into one team is the better shape, for the same reason `research`
isn't a fixed pipeline: if the risk review finds a problem, it needs to
send the strategy back for another enhancement round, and a fixed
sequence can't do that — it needs a manager that can loop.

**Role:** given a strategy spec from `strategist`, improve it and stress
it before it's allowed anywhere near `risk_gatekeeper`. Three specialist
roles inside one team, run by one manager that decides ordering and
whether to loop again:

1. **`enhancer`** — tunes the spec's parameters (stop distance, sizing,
   entry threshold, ...). **Critical design rule:** the actual parameter
   sweep / Monte Carlo search must be real, deterministic Python — a tool
   (`run_parameter_sweep`, sitting on top of the separately-planned
   walk-forward backtest harness) that runs an entire sweep internally in
   one call and returns a compact results table. Not the LLM computing
   numbers trial-by-trial — with local-model latencies measured at
   14–276 seconds *per call* during the real screener test, an
   optimizer that round-trips through the LLM once per parameter
   combination would take hours for something that should take seconds.
   The LLM's job is choosing which region to explore next and interpreting
   whether an improvement is real or noise — a handful of calls per
   tuning run, not one per trial.
2. **Risk debate — `bull_advocate` + `bear_advocate` + `risk_officer`**
   (the concrete shape borrowed from Vibe-Trading's `investment_committee.yaml`,
   see §5 below — this is a better mechanism than what we originally
   sketched). Bull and bear run in true parallel with **no visibility into
   each other's output**, and each is *required* to argue the strongest
   case against their own position (bull's own final section must state
   the main risk to the bull case; bear's must state what would disprove
   the bear case — this forces genuine steelmanning, not a rubber-stamp).
   A third role, `risk_officer`, never sides with either — it scores each
   individual point from both sides for reliability, checks bull for
   confirmation bias and bear for excessive pessimism, and explicitly
   names blind-spot risks *neither* side raised. Disagreement between bull
   and bear becomes a real, structured input to `risk_officer`'s synthesis
   instead of being silently averaged away.
3. **`paper_trader`** — takes the (possibly re-enhanced) spec and runs it
   through a real historical week bar-by-bar, like a rehearsal of live
   trading. Same principle as `enhancer`: the actual trade execution and
   bookkeeping is a real tool call (reuses `run_backtest`/vinu-simulator,
   the same one `research`'s `backtest_runner` already calls) — the
   specialist's job is to read the day-by-day output and narrate what
   happened, flag anything implausible, not compute P&L itself.

**Output:** a strategy spec with real backtest/paper-trade metrics
attached, plus the risk_officer's synthesis, ready for `risk_gatekeeper`.

### 5. `risk_gatekeeper` — proposed

**Role:** the last check before a strategy spec becomes a real order —
different question from `strategy_lab`'s risk debate. `strategy_lab` asks
"is this strategy sound on its own terms." `risk_gatekeeper` asks "does
this fit within the portfolio's *actual current* exposure and capital
right now" — position sizing vs. account size, correlation to what's
already open, max concurrent risk.

**How it works:** one spec in, one verdict out — `APPROVED` / `REJECTED`
(same `VERDICT: PASS/STOP` shape `research`'s `risk_critic` already uses),
with the specific rule that drove the decision. Rejections go back to
`strategist`, not to a dead end — a rejection is real signal ("too large
given current exposure") the next proposal should account for.

**Real, unresolved dependency:** needs a `get_portfolio_exposure`-style
tool backed by actual live position data, which doesn't exist yet — the
broker/position-tracking layer is only a test connection today, flagged
as deliberately deferred in the original architecture doc.

**Open question:** is this always an in-conversation check (a person
reviewing a proposed trade with the orchestrator), or does whatever
component actually submits orders call it directly, non-interactively?
Likely needs to support both — not decided.

### 6. `capital_allocator` — proposed (new; this came directly from the reference-repo research, not from the original brainstorm)

**Role:** every team so far operates on one symbol/strategy at a time.
Nothing decides, across *all* currently-approved candidates competing for
a shared, finite risk budget, which ones actually get funded. That's this
team's job — turns the pipeline from a hallway (one idea walks through
alone) into a marketplace (many vetted ideas competing for capital).

**Why this is a real, unclaimed gap, not a "nice to have":** checked all
three reference repos in depth (Vibe-Trading, FinRobot, fincept-terminal —
see §5). None of them have this for real. Fincept's persona
"portfolio_manager" agent even has an elaborate prompt describing
Kelly-criterion / mean-variance allocation — and its actual backing tool,
`allocate_capital`, returns a **hardcoded static dict literal** regardless
of input. It's decorative. Nobody has actually built cross-strategy
capital arbitration. This is a genuine opportunity, not a reinvention.

**Status:** least fleshed out of the 8 — needs its own design pass before
it's buildable (what's the actual allocation math — Kelly? fixed-fraction?
risk-parity? — not decided; this doc doesn't pretend to have already
solved it).

### 7. `trade_monitor` — proposed, and this is the one that doesn't fit the normal trigger shape

**Role:** while a position is open, periodically re-check it against fresh
angle data and the strategy's own shadow twin (see §4.5 below), and
recommend hold / flag-for-attention / suggest-exit. **Never places,
modifies, or cancels a real order itself** — only recommends. Whatever
executes trades (outside vinu-agent, "Phase 6" in the existing project
terminology) decides whether to act.

**Why it can't use the normal trigger:** every other team is invoked
because a person is mid-conversation asking for something.
`delegate_to_team` is a synchronous, blocking call from inside one
orchestrator turn — fine for that. A position can stay open for hours or
days across many separate sessions with nobody chatting. Modeling that as
one long blocking call would stretch the orchestrator's `AgentLoop` into
something it was never built for.

**The actual fix — no new vinu-agent mechanism, just a different caller:**
`TeamManager` is already a plain, directly-constructible class — proven
for real by a test script that built one and called `.run(...)` with zero
orchestrator involvement. So: an external scheduler (doesn't exist yet —
a simple poller is enough) wakes up every N minutes per open position and
constructs `TeamManager` directly, the same way. Each invocation is short
and bounded — "check this one position right now" — not one
continuously-open call. Same `team_runs`/`team_tasks` tracking, same
LLM-call logging, zero new plumbing inside `vinu_agent` itself. The only
genuinely new thing is a small external component (the scheduler) living
outside vinu-agent entirely.

**Real, unresolved dependency:** needs a `get_open_position_status`-style
tool (current price, unrealized P&L, time held, link back to the original
strategy spec) — same missing "real position data" gap `risk_gatekeeper`
is blocked on. Likely the same underlying tool serves both.

### 8. `post_trade_review` — proposed

**Role:** after a position closes, compare what actually happened to what
was predicted, and write down *why* — which part of the original
reasoning held up, which didn't. Not the win/loss stats
(`pnl_attribution`, an existing vinu-initial-analysis angle, already does
that correctly) — the narrative "why," which that angle's own design doc
explicitly flags as outside its current scope.

**This team's trigger already exists in the project — not invented here.**
A real trade close already fires a real event:
`POST /pnl-attribution/{symbol}/record`, confirmed directly against the
real `pnl_attribution` design doc and the real `Position` schema in
`vinu-live/vinu_live/book/schema.py`. Every closed `Position` already
carries an `artifact_id` linking back to the trade plan that authored it —
exactly what this team needs to find the original strategy spec, with no
new signal or lookup mechanism needed. Same non-orchestrator
`TeamManager`-direct-construction pattern as `trade_monitor`, triggered by
whatever already handles the close event.

**Made sharper by the shadow ledger (§4.5):** instead of comparing against
one static prediction, this team can pull the shadow twin's *entire path*
at close time — "the original plan, left alone, would have done X; what
we actually did, with N interventions along the way, did Y." A much
richer story than a single predicted-vs-actual point.

**Output:** lessons that flow back to `strategist` as input for the next
cycle on that symbol/setup — feedback, never an automatic change to any
live strategy.

## 4. Shared mechanisms (not teams — infrastructure that makes every team above better)

These apply *across* teams. Building any of them as its own team would be
the wrong shape — they're either structural checks inside `TeamManager`
itself, shared tools, or config knobs.

### 4.1 Verify the manager, don't trust it

**The bug that motivated this:** the real `screener` test (§3.1) — the
manager's final answer claimed "persistent timeouts" when the actual
`team_runs`/`team_tasks` records showed both specialist delegations
completed successfully. An LLM synthesizing a final answer can just be
wrong about its own history, and nothing catches that today.

**The fix:** a small, non-LLM check inside `TeamManager`, applied to every
team's final output, that cross-references the manager's claims against
the real task/run records before the result is allowed to surface upward.
If the manager says "timed out" but the task row says `completed`,
block/flag it rather than pass it up silently.

**Confirmed as a real, unsolved problem elsewhere too:** Vibe-Trading (the
most sophisticated reference repo found) has *three* real, working
verification mechanisms — a deterministic classifier that rejects a
worker's "I'm done" if it made zero tool calls despite having data tools
to use; a goal-completion gate that requires every claim to resolve to a
SHA256-hash-verified artifact on disk (enforced by raising an error, not a
prompt instruction); a report-auditor that samples ~15% of a report's
numeric claims and fails the whole report if any is off by more than 1%.
**But even Vibe-Trading has our exact bug** — its own top-level DAG
aggregator writes the final report straight from the last LLM's summary,
with no check against the real per-task status records underneath it.
Nobody has closed this loop at the synthesis level. Worth building for
real, and worth borrowing the "sample and check numeric claims" idea from
the report-auditor pattern specifically for anything `strategy_lab` or
`post_trade_review` reports with real numbers.

### 4.2 Per-symbol / per-setup persistent memory

**The problem:** "lessons feed back to strategist" was, until this
section, just an arrow on a diagram with nothing concrete behind it.

**The mechanism:** a ledger — what's been tried on this symbol/setup
before, what held up, what didn't — that `strategist` (and `strategy_lab`)
must consult before proposing again, not an optional tool they can skip.

**What a good version of this looks like, borrowed from real code:**
Vibe-Trading's `HypothesisRegistry` — each hypothesis carries a status
(`exploring | testing | validated | rejected | monitoring`), links to real
backtest evidence, and is full-text searchable by symbol/title/thesis.
Genuinely good shape to copy directly. The gap even Vibe-Trading has:
registering/consulting it is opt-in tool use nobody is forced to do — our
"must consult before proposing" rule is the actual improvement over what
exists anywhere we looked.

### 4.3 Cost-based model routing

**The problem:** real screener test showed per-LLM-call latency ranging
14.77s to 276.44s on the local model in use. Most of what `trade_monitor`
will do, most of the time, is "nothing's changed, keep holding" — that
doesn't need the same model as a deep risk debate or a post-trade
narrative.

**The mechanism:** vinu-agent already has per-tier LLM config for the
orchestrator (opt-in via env vars, falls back to the shared config when
unset). Extending the same pattern down to specialist level — cheap/fast
model for routine, frequent checks; stronger model for rare, deep
reasoning.

**Confirmed cheap and real, but nobody actually does it:** every reference
repo checked has the *hook* for this (a config field letting one call site
override the model) but not a real routing policy — Vibe-Trading's
`SwarmAgentSpec.model_name` exists and is used by **zero of 29** real
presets. Fincept has the same pattern in exactly two call sites
(`reflector_model`, `distill_model`), manually set, no general logic. This
confirms the pattern is trivial to add and nobody bothers — worth just
doing it rather than over-engineering a general router.

### 4.4 Debate/ensemble specialist pattern

Not a standalone team — this is *how* `strategy_lab`'s risk role is
composed (§3.4, item 2: bull + bear + risk_officer). Documented here
separately because it's a reusable pattern, not unique to `strategy_lab` —
could also apply to `risk_gatekeeper` later if a single risk voice there
turns out to be too narrow.

**Where this came from:** Vibe-Trading's `investment_committee.yaml` is
the strongest real implementation found across all three repos — true
parallel bull/bear with no shared visibility, each required to argue
against their own position, and a named third role synthesizing via a
structured reliability scorecard rather than a naive average.
**Contrast, as a cautionary tale:** fincept-terminal's README advertises
"37 debating agents" (Buffett, Graham, Lynch, Munger, ...) — the real code
runs every persona completely independently with **zero aggregation
anywhere**. The debate/synthesis code that does exist in that repo isn't
even wired to the personas. Worth remembering when evaluating any
framework's marketing copy against its actual code.

### 4.5 The shadow ledger — continuous paper twin, not a one-time gate

This one deserves its own explanation since it's easy to leave vague (as
an earlier pass at this document did).

**The idea:** once a strategy goes live via `risk_gatekeeper` +
`capital_allocator`, keep a **paper twin** of the *original, unmodified*
plan running in parallel for the whole life of the position — so at any
point, "what would this position be doing right now if we'd left it
alone" is a real, computed answer, not a guess.

**Why this is not a 9th team:** the twin's bookkeeping — simulate fills
against the original rule using the same price feed, no live-position
adjustments applied — is pure deterministic math. No judgment involved.
Same category as the parameter sweep in `strategy_lab`: it should be a
plain background tool, not an LLM's job.

**The actual mechanism, concretely:**

1. **`shadow_ledger`** (new infrastructure, not a team) — when a strategy
   goes live, the same spec spawns a simulated paper position here. It
   updates continuously off the same price feed, tracking what the
   *original* plan would be doing, completely independent of whatever
   real adjustments happen to the live position. No LLM involved at all —
   same spirit as Vibe-Trading's real, continuous `decay.py` rolling
   monitor (rolling performance vs. baseline, a state machine, no LLM in
   the loop) found during the repo research.
2. **`trade_monitor` gets a new tool** — `get_position_comparison(symbol)`
   — returning both the real position's current state (from the broker
   layer) and the shadow twin's current state from the ledger, side by
   side. Every periodic check `trade_monitor` runs now reasons over both
   numbers: "real is down 2%, the untouched shadow is flat — the
   adjustment we made is costing us, worth reconsidering" is a concrete,
   checkable claim instead of a vague hold/flag call.
3. **`post_trade_review` reads the same ledger at close time** — instead
   of comparing against one static prediction, it gets the shadow twin's
   *entire path* over the life of the trade: what the original,
   unmodified plan would have done, versus what actually happened with
   however many interventions occurred along the way. Turns "how it
   should have been" from a guess into a real comparison.

**What real repos have, and what they don't:** none of the three
reference repos have a true live-vs-shadow twin. Vibe-Trading's
`shadow_account` is confusingly named — it's a one-shot extraction of
behavioral patterns from *past* trades, not a running parallel account.
Fincept's `agno_trading` runs a genuinely continuous paper loop, but for N
competing *models* racing each other, not a twin of one live strategy.
This gap is real and unclaimed — the mechanism above is original to this
design, not borrowed.

## 5. Reference-repo research — summary of what was checked and why it matters

Three repos were read in real depth (source code, not just READMEs) for
patterns applicable to this design:
[C:\Users\vinay\Desktop\my-trading-work-3\personal-important\other-reference-repos](../../personal-important/other-reference-repos):

- **Vibe-Trading** — closest in spirit to vinu-agent's own architecture
  (a swarm/DAG-of-workers system, real live-trading enforcement code, real
  memory/hypothesis/strategy-lifecycle stores). The single most useful
  repo of the three — supplied real, concrete patterns for §4.1 (worker
  output classifier, evidence-hash-verified goal completion), §4.2
  (`HypothesisRegistry`), §4.4 (`investment_committee.yaml`'s bull/bear/
  risk_officer debate), and confirmed §4.3's cost-routing hook exists but
  is unused. Also the source of the filesystem-based kill switch and
  fail-closed data policy noted below.
- **FinRobot** — an AutoGen-based multi-agent framework for financial
  *report generation*, not a running trading/risk system. None of the 6
  original ideas had a real equivalent here — its "multi-agent" layer
  turned out to be regex-triggered nested chats for routing large text
  around context limits, not genuine verification or synthesis. Useful
  mainly as a negative result and one cautionary anti-pattern (bracket-
  tag string matching for manager→specialist handoff — more fragile than
  vinu-agent's tool-call-based delegation).
- **fincept-terminal** — a large native terminal app with four
  *non-interoperating* agent subsystems bolted on. Its persona-agent
  factory (`finagent_core`) validated the memory-isolation approach
  (per-`agent_id` scoping, tested directly) and supplied the two real
  cost-routing call sites. Its headline "37 debating agents" claim turned
  out to be unsubstantiated by the actual code (§4.4) — a useful reminder
  to verify a framework's real behavior against its marketing.

**Ideas confirmed as genuine, unclaimed gaps across all three repos** (i.e.
not just missing from vinu-agent's current design, missing everywhere
checked): `capital_allocator` (§3.6) and the continuous shadow twin
(§4.5). These are the two most original pieces of this whole design.

**Other strong patterns found, not yet folded into any team above** (flagged
for awareness, not yet decided where they'd live in vinu-agent):

- **Filesystem-based kill switch** (Vibe-Trading) — a single file's
  existence is the sole authority to halt live trading, checked before
  every order, independent of any agent-loop state — deliberately
  designed to hold even if the LLM is wedged or non-cooperating. Lines up
  with vinu-agent's own already-deferred `broker/kill_switch.py` work —
  good outside confirmation the direction is right.
- **Fail-closed as a blanket policy** — every risk check treats missing or
  unparseable data as automatic deny, never "assume it's fine." A
  one-line policy worth stating explicitly for `risk_gatekeeper` and
  `capital_allocator` both.
- **Never auto-resend on ambiguous state** — on crash/restart, if it's
  unclear whether a real order went through, halt and surface it, never
  guess or auto-correct. The single sharpest idea found for anything
  touching real broker side effects — relevant to whatever eventually
  sits at the Phase 6 execution boundary.
- **Persona identity stability across solo vs. team-nested invocation**
  (fincept) — the same specialist reuses the same memory/session whether
  invoked directly or nested inside a team's delegation. Worth checking
  vinu-agent's own `TeamManager` for this before it becomes a real bug,
  once a specialist can plausibly be called both ways.

## 6. Open decisions (not yet settled — listed so they aren't silently assumed later)

1. Exact JSON shape of the strategy spec `strategist` produces — needed
   before `strategy_lab`, `risk_gatekeeper`, and `capital_allocator` can
   all be built consistently against it.
2. Whether `risk_gatekeeper` should be folded into `strategy_lab` (making
   it 7 teams instead of 8) — kept separate in this doc because they
   answer different questions (strategy soundness vs. current-portfolio
   fit), but this is a judgment call.
3. `capital_allocator`'s actual allocation math — Kelly criterion,
   fixed-fraction, risk-parity, something else — not decided; this is the
   least-fleshed-out team of the 8.
4. Whether `risk_gatekeeper` is always an in-conversation check or can be
   called non-interactively by whatever submits real orders — likely
   needs both, not decided.
5. `research`'s `idea_generator` staying angle-blind — intentional
   (unconstrained brainstorming) or a real gap to close — not decided.
6. Poll interval and alerting story for `trade_monitor` — fixed vs.
   adaptive interval, and what happens to a `suggest-exit` recommendation
   if nobody's watching — not decided, depends on a broader alerting
   design out of scope here.
