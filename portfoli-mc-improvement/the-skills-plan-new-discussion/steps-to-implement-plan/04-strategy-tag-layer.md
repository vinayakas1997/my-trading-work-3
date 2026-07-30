---
name: 04-strategy-tag-layer
status: Not Started
phase: 2
code: B2
depends_on: []
unlocks: [07-optimizer-rules-skill]
---

# Step 04 — Strategy Descriptive/Tag Layer

## Why this step

The self-research loop the whole plan is built around needs the agent to be
able to answer "does another strategy align with this one" when a strategy
under test isn't working — without re-reading every strategy's full
definition each time. We originally planned a brand-new `strategy-catalog`
skill with its own `catalog.yaml` duplicating a list of strategies. Then we
found `vinu-strategy/engine/registry.py`'s `StrategyRegistry.load_all()`
already reads every strategy from YAML into `StrategyConfig` objects, keyed
by name — a catalog already exists. Building a second, parallel one would
immediately drift out of sync with the real one. This step is a *tag layer*
on top of the existing registry, not a replacement for it.

## What we're achieving

A lightweight, structured metadata layer — regime (`trend-following` /
`mean-reverting` / etc.), style, and `indicators_used` — keyed by the same
strategy names `StrategyRegistry` already uses, so "find something aligned
with strategy X" becomes a filter over tags instead of a re-read of full
strategy prose. Exactly how this data is stored (a companion YAML the agent
reads alongside the registry's files, or new fields added directly to each
strategy's existing YAML) is an open decision for substep 1 below — resolve
it by checking which is less invasive to the existing `StrategyConfig`
loader.

## Where it matters in the future

Step 07's self-research loop uses this the moment a swept strategy fails
gatekeeping and needs to check whether a related strategy might do better
before giving up or escalating. Without tags, that check either doesn't
happen (the agent just gives up) or is prohibitively expensive (re-reading
every strategy's full text every time).

## How it connects to other steps

- **Independent of Steps 01–03** — nothing here depends on the verification
  pass or tool wiring; this can be built any time, in parallel with
  everything else in Phase 2.
- **Feeds Step 07** — the optimizer-rules skill's "check if another
  strategy aligns" behavior is only possible once tags exist to filter on.

## Substeps

1. Read `vinu_strategy/models/strategy.py`'s `StrategyConfig` fully.
   Decide: does adding `regime`/`style`/`tags` fields directly to
   `StrategyConfig` (extending the existing model) make more sense than a
   separate companion file? Prefer extending the existing model unless it's
   used somewhere that would break from new optional fields — check
   `vinu_strategy/loader.py` and `server/routes_read.py` for anything that
   would choke on unexpected keys.
2. If extending `StrategyConfig` is safe: add `regime: list[str]`,
   `style: str`, and confirm `indicators_used` is already derivable or
   needs adding, then backfill existing strategy YAMLs with real tags (not
   placeholders — read each strategy's actual logic to tag it honestly).
3. If extending isn't safe: build a companion `skills/strategy-tags/`
   skill whose `tags.yaml` is keyed by the exact same strategy names
   `StrategyRegistry.load_all()` produces, and document in its `SKILL.md`
   that this is metadata *about* strategies in the registry, not a
   replacement catalog.
4. Write the alignment-matching logic description (in whichever `SKILL.md`
   ends up hosting this) — e.g. "same regime + at least one shared
   indicator = candidate aligned strategy."

## Open risks / assumptions

- Assumes `StrategyConfig`'s consumers (loader, API routes, `vinu-portfolio`'s
  `_list_yaml_strategies`) tolerate new optional fields without breaking.
  Verify this before choosing the extend-in-place approach over a companion
  file.

## Definition of done

- [ ] Decision made and justified: extended `StrategyConfig` vs. companion
      file — written down, not just decided in someone's head.
- [ ] Every existing strategy has real (not placeholder) regime/style/
      indicator tags.
- [ ] Alignment-matching rule documented in prose an agent can follow.
