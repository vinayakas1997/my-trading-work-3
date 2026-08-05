---
name: stage1-planning
status: discussion-phase
purpose: the build sequence for stage 1 (the pre-analysis stage) — what to think through first: the data layers (vinu-news, vinu-stock-price), the angles, the full-analysis framework, and then the agentic-analysis framework. Pure stage-1 planning, no implementation.
---

# Stage 1 Planning — The Build Sequence

> **Note:** this file is **purely about stage 1 (the pre-analysis stage)**.
> Stage 2 (live trading) and stage 3 (during/post-trade) are **not considered at
> all** here — they are out of scope, deliberately excluded, and should not be
> thought about, planned for, or designed while reading this file. When the user
> refers to "the project" in this context, it always means stage 1 only.
>
> They only appear in `02-storage-plan.md` for information; this file is strictly
> the stage-1 build order.

## The build sequence (bottom-up dependency chain)

**Step 1 — vinu-news:**
- what analysis it produces
- what gets stored (the L1/L2 feature layer)

**Step 2 — vinu-stock-price:**
- what analysis it produces
- what gets stored (price/K-line layer)

**Step 3 — Decide the angles (the bridge layer):**
- which existing angles are still needed, which are not
- which new angles to add
- for each angle: **input** (which data from steps 1/2), **output**, **how it's stored**
- **how angles access the pre-data** from vinu-news + vinu-stock-price (the shared access contract)

**Step 4 — The full-analysis framework (stage 1):**
- the whole analysis pipeline assembled from steps 1–3
- the thing that runs on the fixed `[start, Qn]` window

**Step 5 — The agentic-analysis framework (research, simulator, agents):**
- its own inputs
- its data-access methods (against a *stable* analysis layer, not raw data)
- how it stores its own analysis results

## The logic that makes it right

- **Data first** (steps 1, 2) — you can't decide angles until you know what raw
  material exists.
- **Angles second** (step 3) — they're defined *by* their inputs from 1/2 and their
  outputs to 4.
- **Framework third** (step 4) — it assembles the angles + the quarterly-run/storage
  plan.
- **Agentic last** (step 5) — it consumes the *output* of step 4, so it must be
  built against a stable analysis interface, never raw data directly.

## One nuance to keep in mind

Step 3 has a chicken-and-egg risk: "how angles access pre-data" (the access
contract) is partly decided by *storage*. So the storage plan (`02-storage-plan.md`)
is the *preliminary* storage thinking; the definitive storage decisions land across
steps 3–4, once you know what every angle actually stores.

## Related files

- `02-storage-plan.md` (same folder) — the storage tiers and open design questions
- `project-explanation.md` (same folder) — the project picture, phases, and goals
- `differnt-combination-analysis.md` (same folder) — the combination matrix
- `../01-news-analysis-methods/` — the news-side research (L1–L4)
- `../02-price-analysis-methods/` — the price-side research (Kronos, TSFM)
