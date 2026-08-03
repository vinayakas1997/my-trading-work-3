---
name: forced-ground-truth-injection
component: vinu-agent
status: implemented
---

# Item 2 — Forced Ground-Truth Injection

## Where to fetch the details

- Reference pattern, read in full: `personal-important/other-reference-
  repos/Vibe-Trading/agent/src/swarm/grounding.py` — before a worker starts
  reasoning, it scans for tickers, force-fetches real OHLCV, and injects a
  "Ground Truth" block with an explicit instruction not to cite prices from
  training data. Summarized in `../03-advanced-patterns-from-reference-
  repos.md` §"Forced fresh-data verification."
- The concrete failure this closes: `02-the-1-month-back-testing/testing-
  status/day-stepper-replay-harness/test-log.md`, Bug-5 — the agent placed
  one trade on day 3, then made **zero tool calls** for 16 of the remaining
  17 simulated days, re-issuing the same paragraph with a new date stamped
  on it. Root-cause hypothesis: token-budget starvation as the reused
  session's history grows (`max_tokens=4096` vs. the configured `8000`).
- Codebase gap this fixes: `../02-vinu-components-where-how.md`'s "forced
  daily ritual" and "structured working memory" rows (→ see 03).

## Why

Right now, whether the agent re-checks reality on any given turn is
entirely the model's choice — nothing structurally forces it. The replay
showed that choice fails silently under real conditions (growing context,
shrinking completion budget): the agent didn't error out, it just quietly
stopped checking and kept talking as if it had.

## Impact

This is the cleanest fix for "agent stops calling tools and goes quiet,"
because it doesn't try to detect the dropout and force a retry after the
fact — it removes the model's ability to skip the check at all, by loading
fresh data into context *before* reasoning starts. Whether the model
"chooses" to call a tool becomes irrelevant for at least the positions it
already holds.

## What decision-dots this connects to for the future

- Directly implements two of `01-quant-agent-qualities.md`'s consciousness
  qualities at once: "a forced daily ritual, not a suggested one" and "a
  hard line between fact and belief" (the injected block is explicitly
  tagged as fresh/sourced, vs. anything the model recalls from earlier
  turns).
- Upstream dependency for item 3 (structured decision journal) — a journal
  fed by unforced, possibly-stale reasoning isn't worth building. Item 3
  should not start until this item's injection is in place and verified.
- Session-hygiene interaction to watch: `AgentLoop`'s three-tier context
  compaction (`_apply_context_layers`, `vinu_agent/agent/loop.py`) must not
  be allowed to compact away *this turn's* injected ground-truth block —
  compacting old prose is fine, compacting away today's forced check is
  exactly the failure mode `01` warns about under "session hygiene that
  doesn't erode the ritual."

## Implementation

- **Plug-in point**: `ContextBuilder` (`vinu_agent/agent/context.py`) —
  it already assembles system prompt + raw history + current message with
  no compaction/tagging logic of its own, so this is additive, not a
  rewrite.
- Before each turn's prompt is assembled: scan session state for symbols
  that matter this turn — currently held positions at minimum (per `01`'s
  "its own true state, always fetched live, never recalled" rule), plus
  any symbol mentioned in the incoming user message.
- Force-fetch fresh price (and, if in scope, `get_news`) for each of those
  symbols via the same tool clients the agent would otherwise call —
  reusing the actual tool implementations, not a separate fetch path, so
  there's only one source of truth for "how do we get a price."
- Inject a "Ground Truth" block into the assembled context with an explicit
  fetch timestamp per value and an instruction not to state a price for
  these symbols from memory when this block is present — mirroring
  `grounding.py`'s instruction wording.
- **Wiring**: follow the existing per-session attribute-injection pattern
  (`vinu_agent/tools/__init__.py:26-51`, `build_registry()`'s `hasattr`
  check) rather than inventing new plumbing — same rule the backtest plan's
  item 1 (`_as_of`) followed, called out in `AGENTS.md`.
- Explicitly out of scope for the first pass: forcing this for every
  symbol ever mentioned historically in the session, or for symbols on a
  watchlist with no position — start with held positions only, the
  highest-stakes case the replay actually failed on, and widen later if
  needed.

## Files touched

- `vinu-agent/vinu_agent/audit/ground_truth.py` — new: GroundTruthInjector force-fetches prices for held symbols via StockPriceTool + open theses via vinu-research hypotheses API
- `vinu-agent/vinu_agent/audit/__init__.py` — new: package init, exports GroundTruthInjector
- `vinu-agent/vinu_agent/agent/context.py` — ContextBuilder accepts `ground_truth_injector`/`held_symbols`; `build_messages` injects `<ground-truth>` system message after system prompt; exposes `last_ground_truth_msg`
- `vinu-agent/vinu_agent/session/service.py` — `_run_with_agent` resolves held symbols via broker, wires injector; passes `services_config` and `session_id`
- `vinu-agent/vinu_agent/agent/loop.py` — `_auto_compact` preserves `_ground_truth_system_msg` across summarisation; `_ground_truth_system_msg` attribute set from ContextBuilder

## Bugs and fixes

_None yet. Log entries here as they're found during implementation —
symptom, date, reproduction, root cause, fix, verification, status._
