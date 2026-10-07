# Situation 33: caller params missing max_weight/cash_floor crashes WeightPipeline

**Question**: `WeightPipeline.run()`'s risk stage merges two sources of
`max_weight`/`cash_floor` — the strategy's own YAML `pipeline.risk.params`,
and a generic `params` dict the caller passes in (service-level default).
What happens when the strategy YAML doesn't set a risk param, and the
caller's `params` dict also happens to omit it?

**Where**: `vinu-strategy/vinu_strategy/engine/pipeline.py::WeightPipeline.run()`
(the risk-params merge, ~line 50-53) and `vinu_strategy/engine/risk.py`
(`risk_normalize`/`risk_shock_aware`, which read `params.get("max_weight", 0.25)`).

**How tested**: called the real `WeightPipeline.run()` (not a mock of any
part of the pipeline) with a strategy config whose `risk` stage has no
`max_weight`/`cash_floor` params, and a `params={"cash_floor": 0.1}` dict
(missing `max_weight`) — the same shape a second, currently-hypothetical
caller (a backtest tool, a new API route) would plausibly construct:

```python
cfg = StrategyConfig.from_dict({... "pipeline": {... "risk": {"method": "normalize"}}})
p = WeightPipeline()
p.run(config=cfg, universe=["AAPL", "MSFT"],
      feature_signals={"AAPL": {"signal": 1.0}, "MSFT": {"signal": 1.0}},
      params={"cash_floor": 0.1})
```

**Observed (before fix)**: real crash, not a bad value —
`TypeError: '<' not supported between instances of 'NoneType' and 'float'`
in `_risk_normalize_with_shorts`. Root cause: `pipeline.py` did
`risk_params.setdefault("max_weight", params.get("max_weight"))` — when
`params.get("max_weight")` is `None`, `setdefault` still *inserts* the key
with value `None`. `risk.py`'s own `.get("max_weight", 0.25)` fallback never
fires because the key now technically exists (just holding `None`), so
`max_w = None` flows straight into `min(w, max_w)`.

The one current production call site
(`vinu_strategy/service.py:113-116`) always supplies both keys from
`ServiceConfig` (itself always a parsed `float`, never `None`), so this
specific crash is **not reachable today** — but it's a landmine in a shared,
multi-stage pipeline function of exactly the kind a second caller trips over
without warning.

**Verdict**: **bug found and fixed**. Changed `pipeline.py` to only
`setdefault` when the caller's `params` value is not `None`, so an absent
key stays absent and `risk.py`'s own default actually fires. Re-ran the
exact repro post-fix: returns `{"AAPL": 0.25, "MSFT": 0.25}` (the correct
0.25-cap default), no crash. Added
`test_params_missing_max_weight_falls_back_to_risk_stage_default` to
`tests/test_pipeline.py`; confirmed via `git stash` on just
`engine/pipeline.py` that this test fails with the exact same `TypeError`
against the pre-fix code, then restored the fix.

Also confirms `vinu-strategy`'s own engine internals (`selection.py`,
`allocation.py`, `timing.py`, `risk.py`, `rules_engine.py`) were genuinely
untouched by the prior `research-discussion-v2` audit — that audit's
"Research & backtest" pipeline named `vinu-strategy` in scope, but every
actual finding (#31-#43) landed in `vinu-simulator`/`vinu-research` instead.
