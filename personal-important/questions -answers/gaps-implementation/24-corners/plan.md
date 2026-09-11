# Plan - 24 Corners Entrypoints + 4 Next

Goal: Sec1 closed, Sec2-5 one by one.

Files touched:
- `vinu-components/vinu-agent/entrypoint.sh:13` 5 workers + mandate + serve.
- `vinu-components/vinu-live/entrypoint.sh:14` 4 workers + serve.
- `vinu-components/vinu-portfolio/entrypoint.sh:4` monitor + serve.
- `vinu-components/vinu-research/entrypoint.sh:4` decay + freshness.
- `vinu-components/vinu-quant-core/Dockerfile:3` stateless.
- Sec2 scripts setup-secrets, run_pipeline:303, run_month_replay.
- Sec3 prompt backtest_safe 10 vs catalog 24 decision.
- Sec4 tests index knob->test table.
- Sec5 unwanted/logs cleanup archive/prune.

Steps:
1. Sec1 done table above. Supervisor Later docs now.
2. Sec2 scripts next. Then Sec3 indicators. Then Sec4 tests. Then Sec5 cleanup.
3. Each: check files, 2-3 gaps, repos if needed, knobs, order, proof.

Knobs: PLANNER/RISK/CAPITAL/SIGNIFICANCE/SKILL/TRADE/SHADOW/FEEDBACK/DECAY/COMPUTE/NEWS/STOCK (see 10+22).
Acceptance: workers supervised logged, scripts ready, decision pinned, test map exists, folders clean.
