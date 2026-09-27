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
# Stage 0 (G2a, research-discussion-v1/complete-plan/01-native-gaps.md):
# same "real, complete, nothing ever invoked it" shape as shadow-worker
# above -- author_trade_plan()/freeze_trade_plan() were reachable, but
# approve_trade_plan() had no scheduled caller, so a frozen trade plan sat
# at CREATED forever and TradePlanOrchestrator.cycle() (which only acts on
# ACTIVE trade_plan artifacts) had nothing to trade.
vinu-live trade-plan-approval-worker &
# Point 2's candle-close poller (missing-pieces-of-system/new-theory-of-
# trading/system-wide-audit-and-design/reverse-engineering/
# 03-poller-and-state-schema.md Part A) -- same "real, complete,
# nothing ever invoked it" gap as every worker above until it's added
# here. Drives the whole live-decision loop (candle close -> state
# tracker -> live_decision_agent -> LiveScheduler's target_weights,
# point 7 option 1) end to end; without this line the loop never runs
# in a real deployment, only in tests.
vinu-live live-decision-worker &
exec vinu-live serve --host 0.0.0.0 --port 8091
