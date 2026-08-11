# DEV-002 — Strategy evaluate rule_trace shows `regime_analysis.regime` key missing from context

- **Component:** vinu-strategy `service.py:evaluate` / `engine/rules_engine.py`
- **Source of expected behavior:** strategy YAML `e2e_easy_sma_crossover.yaml` declares `angles_required: [regime_analysis]` + a `bear_exit` rule reading `regime_analysis.regime`
- **Phase:** 2

## Documented / expected
The strategy's `bear_exit` rule should evaluate the regime angle and zero the weight when regime == "bear".

## Actual behavior
`evaluate` returns a weight but the rule_trace reports:
```
{"rule":"bear_exit","fired":false,"conditions":[{"source":"angles","key":"regime_analysis.regime","operator":"eq","expected":"bear","actual":null,"met":false,"reason":"FAIL: key not found in context"}]}
```
`actual: null` / "key not found in context" — the angle value never reaches the rules engine for the single-symbol evaluate call.

## How discovered
Block 3: inspected `evidence/03-analysis/strategy-evaluate-aapl.json` response `rule_trace` field after a successful evaluate (weight +0.25 produced).

## Impact
MED — the strategy's timing/risk rules silently no-op (rule never fires, no error). Weights still get produced via allocation, but regime-based exit protection (a core part of this e2e strategy) is not enforced during evaluate. This may also explain why the custom backtest showed 0.33 win-rate with regime gating absent.

## Workaround used
None — proceeded with the custom backtest path; noted as deviation.

## Root cause
Suspected — angle signals fetched via `_fetch_angles_for_symbol` are keyed/packaged in a shape the rules engine doesn't find under `regime_analysis.regime` (or the angle fetch returns data the pipeline drops for a single symbol with this YAML shape). Needs a focused debug in `service.py` angle fetch + `pipeline.py` context assembly.

## Status
OPEN

## Evidence
- `evidence/03-analysis/strategy-evaluate-aapl.json` — `rule_trace.bear_exit.conditions[0].actual == null`
