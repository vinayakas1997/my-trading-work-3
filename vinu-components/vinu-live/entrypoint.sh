#!/bin/bash
set -e

# Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
# phase-5-monitor-extend/): before this fix, only the portfolio-rebalance
# worker (below) ever started automatically -- TradePlanOrchestrator's own
# cycle loop (the actual live entry/invalidation-exit/contingency
# authority "Monitor" is supposed to be) and the feedback-loop worker
# (calibration/pnl_attribution/personality-stats/HypothesisRegistry
# write-back) were both real, complete, `while True: cycle(); sleep()`
# implementations that nothing ever invoked. Same "wiring gap, not a
# design gap" shape as vinu-portfolio's own drawdown-monitor fix
# (see vinu-agent/skills/live-safety/SKILL.md, Stage 3) -- mirrored here.
vinu-live-worker --interval 3600 &
vinu-live trade-plan-worker &
vinu-live feedback-worker &
# Scheduler-wiring follow-up (New-talk-agents/new-thinking/new-restructure/
# phases/phase-9-scheduler-wiring/): ShadowEvaluator.evaluate_all() was
# correct and tested since Phase 4 but had no scheduled caller anywhere,
# flagged in every phase record since (4, 5, 7). Same shape as the two
# workers above -- background loop, foreground `serve` still owns the
# container's lifecycle.
vinu-live shadow-worker &
exec vinu-live serve --host 0.0.0.0 --port 8091
