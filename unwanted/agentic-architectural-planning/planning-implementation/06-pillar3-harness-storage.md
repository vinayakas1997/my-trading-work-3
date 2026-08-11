---
name: pillar3-harness-storage
status: proposed-not-built
purpose: concrete answer to pillar 3 (storage for responses and run details, "the harness") from ../archi-think-1.md -- mostly already built, this file confirms coverage and reconciles one piece of the original architecture doc's plan that turned out to be superseded rather than needed.
---

# Pillar 3 — storage for the harness

Reference: [../archi-think-1.md](../archi-think-1.md) (the 9 pillars),
[../../implementation/00-status.md](../../implementation/00-status.md)
(what's already real).

## What's already built and real

- **`team_runs`/`team_tasks`** — one row per delegation, status tracking,
  verdicts, timing. Built, tested against a real LLM.
- **`llm_calls`** — full prompt, response, token counts, latency, on
  *every* LLM call anywhere in the system, tagged by tier/team/agent/
  role. Built, tested.

Between these two, "what ran, what it returned, how long it took, what it
cost" was already fully answered before this architecture-planning pass
started. Pillars 5–7 and 9 added the three genuinely new stores this
required beyond that (`strategy_specs`, `memory_ledger`,
`shadow_ledger_snapshots`) plus two small additions to `team_runs` itself
(`related_spec_id` from pillar 7, `last_heartbeat_at` + `stale` status
from pillar 9). Pillar 3 doesn't need to invent anything further — its
job here is confirming that's actually complete, and reconciling one
thing that isn't.

## One reconciliation: the original `agent_runs/{run_id}/` plan is superseded, not needed

`../../01-orchestrator-and-teams-architecture.md`'s original folder
structure planned a `data/agent_runs/{run_id}/` directory — each team
run's own working trace (manager + specialist internal reasoning) dumped
to disk, separate from session messages. That was written before
`llm_calls` existed. Now that every single LLM call is individually
logged with its full prompt and response, queryable by
`run_id`/`tier`/`team`/`agent`/`session_id`, a raw per-run file dump would
just be a second, coarser copy of what `llm_calls` already stores at
finer granularity (per call, not per run-blob). **Not building
`agent_runs/{run_id}/` — reconciling the plan rather than leaving two
documents quietly disagreeing about whether it exists.**

## Confirming the large-output rule still holds

The architecture doc's existing rule — "large outputs (e.g. full backtest
data) stay as file pointers on disk, not DB blobs" — checked against
every new store from pillars 5–7:

- `strategy_specs`, `memory_ledger` rows — small structured text/JSON,
  fine as plain DB rows, no file-pointer treatment needed.
- `shadow_ledger_snapshots` — the one store with real volume concerns,
  but it's numeric time-series rows (price, P&L, timestamp), not blobs —
  fine as DB rows too. Volume is handled by pillar 6's downsample-and-
  prune policy, not by pushing it to file storage.

No new store from this whole planning pass violates the existing rule —
worth confirming explicitly rather than assuming.

## Net effect

Pillar 3 required no new design of its own — everything it needs was
either already built (`team_runs`, `llm_calls`) or already covered by
pillars 5, 6, 7, and 9. Its only real output is this reconciliation (drop
the now-redundant `agent_runs/{run_id}/` plan) and the confirmation that
nothing new breaks the existing large-output-as-file-pointer rule.
