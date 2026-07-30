---
name: strategy-tags
description: Regime/style/indicator metadata about the strategies already registered in vinu-strategy's StrategyRegistry, keyed by the same names — for finding an aligned strategy without re-reading every strategy's full YAML.
category: tool
---

## Strategy Tags — Metadata About the Real Registry

This is **metadata about strategies that already exist** in
`vinu-strategy/strategies/*.yaml`, read by `StrategyRegistry.load_all()`.
It is not a second catalog — every key in `tags.yaml` must match a real
`name` field from that registry exactly. If a strategy is renamed, added,
or removed there, this file goes stale until updated to match; it does not
create or replace anything.

### Why this exists as a companion file, not a `StrategyConfig` field

`StrategyConfig` already has a free-form `metadata: dict` field that
would have been the natural home for this. It wasn't used, for two
confirmed reasons (read directly from source, not assumed):

1. `vinu_strategy/api.py::get_strategy()` hand-builds its HTTP response
   dict field-by-field and does not include `metadata` — putting tags
   there would make them invisible over HTTP without also patching that
   response shape.
2. `vinu_strategy/server/routes_read.py`'s `GET /strategies` (list) does
   **not** read from `StrategyRegistry`/YAML at all — it queries a
   separate SQLite `strategy_registry` table via
   `service.py::list_strategies() -> meta_storage.get_registered_strategies()`.
   Only `GET /strategies/{name}` (single-strategy detail) reads the YAML
   config. These two routes already draw from two different sources —
   a pre-existing inconsistency in vinu-strategy, not something this step
   introduces or fixes. Extending `metadata` wouldn't make tags visible
   through the list route regardless.

A companion file the agent reads directly (like `gatekeepers/rules.yaml`
and `optimizer-rules/rules.yaml`) sidesteps both issues and doesn't touch
vinu-strategy's existing HTTP contract at all.

### How to use this skill

1. Load `tags.yaml` via `load_support_file("tags.yaml")`.
2. Look up the strategy you're evaluating by its exact registry `name`.
3. To find an aligned alternative when a strategy under test fails
   gatekeeping: **same `regime` (any overlap) AND at least one shared
   `indicators_used` entry** = candidate aligned strategy. This is
   deliberately loose (OR-of-regimes, not exact match) — the point is
   surfacing plausible alternatives to consider, not a strict filter.
4. Report *why* a candidate is aligned (which regime/indicator overlapped)
   — don't just return a name.

### Worked example

`ma_crossover` (regime: `[trending]`, indicators: `SMA_9`, `SMA_21`) fails
gatekeeping on a choppy symbol. Checking `tags.yaml`:
- `adx_filtered_crossover` shares regime `trending` **and** both `SMA_9`
  and `SMA_21` — strong alignment (it's structurally the same crossover,
  just ADX-gated to avoid exactly the choppy conditions `ma_crossover`
  has no defense against). Worth trying before giving up on the symbol.
- `rsi_mean_reversion` shares neither regime nor indicators — correctly
  not surfaced; it's a genuinely different bet (mean-reversion vs.
  trend-following), not a variant.
- `news_aware_momentum` shares regime `trending` but no indicator overlap
  — a weaker, still-worth-noting alignment (same regime, different
  signal family).

### Adding a new strategy's tags

When a new strategy is added to `vinu-strategy/strategies/`, add a
matching entry to `tags.yaml` in the same step — derived from actually
reading that strategy's YAML (`features_required`, the `pipeline`
signal/timing rules, any `angles_required` regime gating), not guessed
from its name. An untagged strategy is invisible to alignment-matching,
not neutral — it will never be surfaced as a candidate.
