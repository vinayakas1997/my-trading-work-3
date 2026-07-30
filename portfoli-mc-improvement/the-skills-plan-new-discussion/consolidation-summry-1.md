Fair — here's the consolidation, then the build order.

Aims (the "why," refined from where we started)
Focus 1 — Parameter sweep. Given a strategy with known indicators, adaptively search its numeric parameter space (coarse→fine, widen if insensitive, narrow if sensitive, governed by expectancy + progress heuristics) to reduce drawdown and raise Sharpe, converging on settings that pass real statistical validation — not a fixed grid.
Focus 2 — Agent actually uses what already exists. The 11 angles, hypothesis evidence, judgment history — all computed and stored already. The agent needs to read them back and let them drive decisions, not compute anything new.
Focus 3 — Progressive daily portfolio. Regime-aware, probability-weighted daily allocation (tickers + cash ratio) that improves from yesterday's outcomes. The safety net around this (circuit breakers, drawdown scheduler) already exists; the allocation intelligence itself doesn't.
Operating principle (the "how," philosophically)
Skills are a knowledge library, not scripts. At runtime the agent composes four things itself: knowledge (skills — what exists, what it means), tools (existing vinu-* services), memory (existing stores — don't rebuild), governor (hard limit + progress heuristic + expectancy heuristic). Self-agency comes from the agent freely combining these, not from a procedure we hand it.

What the sweep actually found
The intelligence layer is mostly already built in code. The consistent, confirmed gap is narrower than "build an agentic system" — it's "the agent can't see or reach most of what already exists."

The work, categorized
A — Genuinely new build (nothing duplicates these):

A1. Parameter-value sweep/grid runner (Focus 1's actual engine — doesn't exist anywhere)
A2. Tool wiring to query HypothesisRegistry / checkpoints / exhaustion / research_catalog granularly (today the agent only has one opaque blocking call, run_research)
A3. Focus 3's allocation intelligence (regime-aware, learning, probabilistic — build_portfolio() is still a stateless risk-parity calc)
B — Knowledge/skill layer (interface work, mostly docs + light structure):

B1. gatekeepers skill, rewritten as an interface to compute_validation_verdict / PBO / correlation-gate / promotion — not invented thresholds
B2. Strategy descriptive/tag layer sitting alongside StrategyRegistry's existing YAMLs (not a new catalog)
B3. Tool catalog, ideally generated from the 19 BaseTool subclasses rather than hand-written
B4. optimizer-rules skill as adaptive-search reasoning principles, feeding off A1 and B1
B5. One short doc chaining promotion-bar (research→active) and circuit-breaker (live monitoring) into one live-safety story
B6. Governor doc (hard limit + progress heuristic + expectancy heuristic), tied to the checkpoint/exhaustion mechanism A2 exposes
C — Already solved, leave alone: statistical validation, hypothesis/evidence tracking, checkpointing, exhaustion tracking, angle execution (AngleRunner), circuit breakers.

Build order — why this order, not another
The trap to avoid: writing a skill that tells the agent to "read X" when no tool can actually fetch X yet. So knowledge-layer work has to follow tool-wiring, not precede it.

A2 first. Nothing else can be honestly written until the agent can actually reach HypothesisRegistry, checkpoints, exhaustion state, and the validation block on a backtest result. This unlocks B1 and B6.
B1 + B2 + B3 in parallel, once A2 lands for B1. B2 and B3 don't depend on A2 at all — they can start immediately, independently, whenever.
A1 (the sweep engine) next. This is Focus 1's centerpiece and the biggest net-new piece of code.
B4 + B6 together, once A1 exists to drive and B1 exists to judge against — the optimizer-rules skill and the governor are one coherent unit and shouldn't be designed apart from each other.
B5 whenever — low effort, no dependencies, mostly writing.
A3 (Focus 3) last, as its own phase — it's the largest and most independent piece, and we already agreed it doesn't block anything else.
That gives three real phases: (1) open the doors (A2) → (2) describe what's behind them (B1/B2/B3) → (3) build the new engine and teach it to reason (A1, then B4/B6) — with Focus 3 (A3) as a separate track afterward. B5 slots in anywhere.

Want me to lock this order and start on A2 (the tool-wiring gap), or does the priority feel wrong somewhere — e.g. would you rather see A1 (the actual sweep) working end-to-end first, even crudely, before investing in the wiring/knowledge layer around it?


Honest answer: close, but not fully — there are a handful of things I inferred rather than confirmed by reading, and a couple of components I never actually opened. Given how many times this exact conversation flipped a confident assumption after actually reading the file, I'd rather flag these now than let them ride into A2.

Things I said I'd check and then never actually did:

vinu-research/llm.py's _build_risk_critic_prompt — I know it exists (saw the import in loop.py), but never read what the risk-critic actually evaluates. B1/B4 assume gatekeepers sits alongside this cleanly rather than overlapping it — that's still an assumption, not a confirmed fact.
loop.py's actual stopping/convergence code — I read the imports (checkpoints, HypothesisRegistry, rank_candidates) but never the loop body itself. B6 (the governor) is written to complement whatever loop.py already does — but I don't actually know its real stopping logic yet, so B6 could turn out to duplicate or contradict it.
Two whole components never opened at all:

vinu-news — never looked at its source directly. Focus 2 specifically calls out "use news_price_causality and shock detection to avoid certain plays" — I only ever saw it secondhand via news_tool.py's existence and the sentiment-analysis skill name. Real gap in the sweep.
vinu-live — same situation. The /broker/halt + OrderGuard claim in B5 came from a comment inside vinu-portfolio/circuit_breakers.py, not from reading vinu-live or routes_broker.py myself. Secondhand, unverified.
One decision left dangling:

I recommended SQLite+FTS5 for the hypothesis/reasoning text search, back before we knew ResearchStorage already existed. I never went back and checked whether sqlite_backend.py's schema already has an FTS5 table, or whether that's still something A2 needs to add.
Two things that got compressed out of the summary but aren't actually gaps — worth restating so they don't get silently dropped: research-discipline (5-bias self-check) already covers the reflection step, and thesis-tracker already covers hypothesis structure/status. Both belong in bucket C, just didn't make the summary's explicit list.

So: the shape of the plan (three phases, A/B/C buckets) is solid — everything in it that I did verify by reading real code holds up. But B1, B4, B5, and B6 each rest on at least one thing above that's inferred or unread. Cheapest fix: one more short pass — read _build_risk_critic_prompt, loop.py's stop condition, and skim vinu-news/vinu-live — before we lock A2 as the starting point, since A2 is exactly the tool-wiring work that needs those answers to be right the first time.

Want me to close those four out now, or note them as known risks and start on A2 anyway?