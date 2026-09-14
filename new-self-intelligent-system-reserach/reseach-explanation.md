# Making vinu-research self-intelligent: Hindsight memory integration

## Sources (verified 2026-09-14, via live web search — not from memory/training data)

- [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) — main repo, MIT license, ~23.6k stars
- [Hindsight docs](https://hindsight.vectorize.io)
- [hindsight-client on PyPI](https://pypi.org/project/hindsight-client/) — `pip install hindsight-client`, latest version 0.8.4 (Jul 2026)
- [hindsight_client.py source](https://github.com/vectorize-io/hindsight/blob/main/hindsight-clients/python/hindsight_client/hindsight_client.py) — read directly to verify real method signatures
- [Introducing Hindsight (Vectorize blog)](https://vectorize.io/blog/introducing-hindsight-agent-memory-that-works-like-human-memory)
- [Hindsight is 20/20 (arXiv paper)](https://arxiv.org/html/2512.12818v1)

Everything below that describes Hindsight's actual API was checked against the real client source file above, not assumed. Where an earlier third-party summary got a detail wrong, that's called out explicitly (see "Corrections" section) — don't trust that summary over what's in this file.

## What problem this solves

`vinu-research/vinu_research/loop.py`'s `StrategyResearchLoop` (confirmed real, `loop.py:124`) is the engine that iteratively generates, backtests, critiques, and refines a trading strategy for one symbol. Today, every part of its "learning" is scoped to a single run:

- `history: list[IterationRecord]` (`loop.py:181`) holds every iteration's strategy code, backtest result, and critic feedback — but it's a local variable, thrown away when `run()` returns.
- `_reflect()` (`loop.py:1294-1312`) — the method that decides whether to pivot, continue, or stop — is a single LLM call fed only the **last 2** iteration summaries (`self._iteration_history_summary[-2:]`, `loop.py:1300`). It has no idea what happened 3 iterations ago, in a previous run on the same symbol last week, or on a different symbol that faced the same regime.
- `_filter_ineffective_suggestions()` (`loop.py:1321`) already tracks, informally, whether a critic's suggestion actually helped within the current run (`self._suggestion_results`) — a primitive memory that proves the *need* for this already exists in the code, it just doesn't persist past one `run()` call.
- Regime knowledge (which strategy template tends to work in trending vs. ranging vs. high-vol conditions) is hardcoded into template selection logic, not learned from what has actually happened.

So the system re-derives the same lessons every single research run, on every symbol, forever. It never gets smarter with age — it just runs the same process more times.

## What Hindsight actually is

Hindsight is a real, actively maintained (MIT-licensed, ~23.6k GitHub stars) agent memory system, distinct from a vector-DB/RAG approach. Its stated design goal is agents that *learn*, not just *recall* — verified via its own README and blog post (sources above).

**Three core operations** (verified against the real client source):

| Operation | What it does | Real method |
|---|---|---|
| **Retain** | Extracts facts/entities/temporal data from content you give it and stores them | `aretain(bank_id, content, timestamp=None, context=None, tags=None, ...)` |
| **Recall** | Searches memory — combines semantic, keyword, graph, and temporal retrieval, then reranks | `arecall(bank_id, query, tags=None, tags_match=..., temporal_window=None, budget="mid", ...)` |
| **Reflect** | Reasons over retained memory to synthesize an answer, shaped by the bank's configured "disposition" | `areflect(bank_id, query, budget="low", tags=None, apply_all_directives=False, ...)` |

**Four memory networks** inside a bank (verified via blog/docs):
- **World** — objective facts ("SPY realized 22% drawdown in the 2022 rate-hike regime")
- **Experience** — the agent's own past actions ("I backtested a 20/50 MA crossover on AAPL, got Sharpe 0.8, failed holdout")
- **Opinion** — subjective beliefs with a confidence score, formed by reflecting over experience+world facts ("momentum tends to fail on AAPL in high-vol regimes" — 0.72 confidence)
- **Observation** — consolidated mental models derived by reflecting across many facts/experiences

**Temporal grounding is built in, not bolted on**: `retain` accepts a `timestamp`, `recall` accepts a `temporal_window` and `query_timestamp`. This is exactly the "when did this hold true" dimension a plain vector-search memory doesn't give you — critical for a trading system, where "momentum works on AAPL" is only true under some regimes, not all of them.

**A bank has a configurable disposition** (`acreate_bank`'s real parameters: `mission`, `disposition_skepticism`, `disposition_literalism`, `disposition_empathy`, or a combined `disposition` dict, plus `reflect_mission`, `retain_mission`, `background`) — this shapes how `reflect` reasons, e.g. a highly skeptical disposition demands more evidence before forming a confident opinion. `reflect` also supports `apply_all_directives=True`, meaning directives are a real concept in the system, just not a parameter you set at bank-creation time (see Corrections below).

## How it extends this system's capabilities

Mapped directly to what's missing today, in priority order:

### 1. Cross-iteration memory within a run, done properly
Right now `_reflect()` sees the last 2 iterations. With Hindsight, every `IterationRecord` (strategy code, Sharpe, max drawdown, trade count, critic verdict/reasoning, and — critically — the regime context at the time) gets `retain`ed as it happens. `_reflect()` becomes a `recall`+`areflect` call that can draw on the *entire* history of this research run, not a 2-item sliding window, and the reasoning is shaped by a disposition tuned for this exact job (skeptical, literal, low-empathy — a quant researcher, not a chatbot).

### 2. Cross-run memory per symbol
Today, if you research AAPL again next month, `StrategyResearchLoop` starts from zero — it has no idea what was already tried and rejected. With a memory bank keyed per symbol (`bank_id = f"research-{symbol}"`), `recall` before generating a new candidate strategy can surface "we already tried RSI mean-reversion on this symbol twice, it failed holdout both times, don't propose it a third time" — turning repeated, wasted research cycles into an actual accumulating body of knowledge about that specific symbol.

### 3. Cross-symbol pattern transfer
A second, global bank (`bank_id = "quant-research-global"`) that every symbol's research run also retains its validated outcomes to lets a *brand new* symbol's first research run recall "here's what has generalized across other tickers in a similar regime" before generating iteration 1 — instead of starting genuinely cold every time.

### 4. Regime-aware "why," not just "what"
Because `retain`/`recall` are temporal and taggable, you can tag every retained memory with the regime it happened under (trending/ranging/high-vol, pulled from the same `trend_lifecycle`/regime angle context this system already computes elsewhere — see `market_regime_analogue.py`). That turns "momentum failed" into "momentum failed *specifically in ranging regimes*" — the regime-conditioned knowledge a static, hardcoded template-selection heuristic can't express.

### 5. Confidence that decays and updates, not a fixed rule
Opinion-network memories carry a confidence score that Hindsight updates as more evidence comes in — structurally the same idea already proven elsewhere in this codebase (TradeScore calibration's correlation-weighted, sample-gated adjustment; `decay.py`'s rolling health evaluation). Hindsight would be doing that same kind of thing for *research-level* beliefs ("is this strategy template still working for this symbol"), not just trade-level scoring weights.

## What it stores, concretely, for this system

| Content | Where it comes from | Why it matters |
|---|---|---|
| Per-iteration strategy code + metrics + critic verdict | `IterationRecord` in `loop.py`'s `run()` | The raw material `_reflect` currently only sees 2-deep |
| Regime context at time of iteration | Existing angle/regime computation (`market_regime_analogue.py`, `trend_lifecycle` angle) | Makes every retained memory temporally *and* regime-conditioned |
| Final verdict + holdout/PBO/stress-test results per completed run | `ResearchRunRecord` / `Artifact` fields already computed | Distinguishes "looked good in-sample" from "actually validated" memories |
| Suggestion effectiveness (`_suggestion_results`) | Already computed, just not persisted past one run | Stops the system re-suggesting things it already proved don't help |
| Cross-symbol validated templates | Successful runs across all symbols, retained to the global bank | Cold-start advantage for a brand-new symbol |

## What NOT to feed it yet

Don't retain live/paper trade outcomes as if they carry the same weight as backtest iteration history — there isn't any real trade history yet (see the paper-trading gate that was found completely disconnected and just fixed this session). Feeding a memory system nothing but backtest chatter and treating its "opinions" as validated is how a system becomes confidently wrong. Backtest-iteration memory is real and available today; trade-outcome memory should only be retained once it's actually produced by real paper/live trading, with itself.

## Corrections to the earlier pasted integration proposal

A prior AI-generated summary of Hindsight (pasted into this conversation) got some details wrong, verified against the real client source (`hindsight_client.py`):

- **`directives` is not a parameter of `acreate_bank`.** The real bank-creation parameters are `mission`, `disposition_skepticism`/`disposition_literalism`/`disposition_empathy` (or a `disposition` dict), `retain_mission`, `reflect_mission`, `background`, plus retrieval feature toggles. Directives are a real concept elsewhere (`areflect` has an `apply_all_directives: bool` parameter), just not set the way the earlier proposal showed.
- **`acreate_mental_model` was not confirmed** to exist in the client's public method list pulled from source. Mental models/knowledge pages are mentioned in Hindsight's docs as a real concept, but the exact SDK method for creating one wasn't verified — check the docs directly before writing code against it.
- Everything else in the earlier proposal (`bank_id`, `retain`/`recall`/`reflect` core shape, the four memory networks, disposition-as-skepticism/literalism/empathy) checked out against the real source.

## Infrastructure cost of doing this

Self-hosting Hindsight requires Docker (or bare-metal via pip) plus PostgreSQL with the pgvector extension (or Oracle AI Database 23ai) — a real new service and a real new datastore, not just a pip install. That's a legitimate infrastructure decision, not a trivial add — factor it in before committing, separately from the "is this a good idea" question, which the rest of this document answers yes to for the backtest-iteration use case specifically.

## Recommended entry point

Pilot this narrowly: wire `retain` into `StrategyResearchLoop.run()`'s iteration loop and `recall`+`areflect` into `_reflect()`, scoped to one symbol's research history first. That's real data available today, a contained blast radius, and a direct, measurable upgrade to a method (`_reflect`) that's currently provably underpowered (2-iteration window, no persistence). Expand to cross-symbol and regime-tagged retrieval only after that's proven out — don't build the global bank and the trade-outcome pipeline before the narrow case has shown it's worth the infrastructure.
