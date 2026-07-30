---
name: 04-strategy-tag-layer
status: Done
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

## What was actually built

**Decision: companion file, not an extended `StrategyConfig`.** Substep 1's
check surfaced two concrete reasons to prefer the companion file over
`StrategyConfig`'s existing (and otherwise perfectly usable) `metadata`
dict, both confirmed by reading source, not assumed:

1. `vinu_strategy/api.py::get_strategy()` hand-builds its HTTP response
   field-by-field and does not include `metadata` — tags placed there
   would be invisible over HTTP without also patching that response shape.
2. `vinu_strategy/server/routes_read.py`'s `GET /strategies` (list) reads
   from a **separate SQLite `strategy_registry` table**
   (`service.py::list_strategies() -> meta_storage.get_registered_strategies()`),
   not from `StrategyRegistry`/YAML at all. Only the single-strategy
   `GET /strategies/{name}` route reads the YAML config. These two routes
   already draw from two disconnected sources — a pre-existing
   inconsistency in vinu-strategy, left exactly as found; not this step's
   job to fix. Extending `metadata` would not have made tags visible
   through the list route regardless of any change made here.

Given both, a companion file the agent reads directly — mirroring
`gatekeepers/rules.yaml` and `optimizer-rules/rules.yaml`'s existing
pattern — avoids touching vinu-strategy's HTTP contract at all.

**Files created:** `project-understanding/skills/strategy-tags/SKILL.md`
and `tags.yaml`, keyed by the 4 real strategy names in
`vinu-strategy/strategies/*.yaml` (`ma_crossover`, `adx_filtered_crossover`,
`rsi_mean_reversion`, `news_aware_momentum`). Every tag was derived by
reading each strategy's actual `features_required`, `pipeline.allocation.signal`,
`pipeline.timing.rules`, and `angles_required` — not guessed from its name.

**Alignment-matching rule** (per substep 4): same `regime` (any overlap)
AND at least one shared `indicators_used` entry. Sanity-checked against
the real 4 strategies: `ma_crossover` and `adx_filtered_crossover` align
strongly (same regime `trending`, share `SMA_9`/`SMA_21` — the latter is
structurally the former with an ADX guard against exactly the choppy
conditions the former has no defense against); `rsi_mean_reversion`
correctly shares nothing with any of the other three (genuinely different
regime and indicator family, a diversification bet not a variant);
`news_aware_momentum` shares regime with the trend-following pair but only
shares an indicator (`ADX_14`) with `adx_filtered_crossover` specifically
— documented in `tags.yaml` as a weaker alignment case. The rule produces
intuitively correct groupings on real data, not just on paper.

**One new distinction surfaced, documented in `tags.yaml`:**
`news_aware_momentum` reads correlation-service signals
(`correlation_required: [impact, granger, drawdown]`) that are not
"indicators" in the `features_required` sense — tracked as a separate
`external_signals_used` field so alignment-matching on "shared indicator"
doesn't conflate the two different signal sources.

## Definition of done

- [x] Decision made and justified: companion file over extended
      `StrategyConfig` — written down in `SKILL.md`'s own "why" section,
      with both concrete reasons cited.
- [x] Every existing strategy (all 4 in the real registry) has real,
      source-derived regime/style/indicator tags — zero placeholders.
- [x] Alignment-matching rule documented in prose, with a worked example
      using the real 4 strategies in `SKILL.md`.
