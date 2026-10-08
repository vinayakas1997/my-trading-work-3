#!/bin/bash
set -e

# A background worker that crashes (non-zero exit) is started again after a growing pause (10 s, 20 s ... 5 min; the count
# resets after 10 healthy minutes). A clean exit (0) ends it. Without this a worker that died at start-up stayed dead while
# the container kept reporting healthy: after the news layer-2 deploy the ingest loop was dead for minutes and nothing said so.
supervise() {
  (
    n=0
    while true; do
      started=$SECONDS
      "$@" && rc=0 || rc=$?
      if [ "$rc" -eq 0 ]; then echo "[supervisor] '$*' finished (exit 0)" >&2; break; fi
      if [ $((SECONDS - started)) -gt 600 ]; then n=0; fi
      n=$((n + 1)); pause=$((n * ${VINU_SUPERVISE_STEP:-10})); [ "$pause" -gt 300 ] && pause=300
      echo "[supervisor] '$*' exited with $rc; restarting in ${pause}s" >&2
      sleep "$pause"
    done
  ) &
}

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
supervise vinu-live-worker --interval 3600
supervise vinu-live trade-plan-worker
supervise vinu-live feedback-worker
# Scheduler-wiring follow-up (New-talk-agents/new-thinking/new-restructure/
# phases/phase-9-scheduler-wiring/): ShadowEvaluator.evaluate_all() was
# correct and tested since Phase 4 but had no scheduled caller anywhere,
# flagged in every phase record since (4, 5, 7). Same shape as the two
# workers above -- background loop, foreground `serve` still owns the
# container's lifecycle.
supervise vinu-live shadow-worker
# Stage 0 (G2a, research-discussion-v1/complete-plan/01-native-gaps.md):
# same "real, complete, nothing ever invoked it" shape as shadow-worker
# above -- author_trade_plan()/freeze_trade_plan() were reachable, but
# approve_trade_plan() had no scheduled caller, so a frozen trade plan sat
# at CREATED forever and TradePlanOrchestrator.cycle() (which only acts on
# ACTIVE trade_plan artifacts) had nothing to trade.
supervise vinu-live trade-plan-approval-worker
# Point 2's candle-close poller (missing-pieces-of-system/new-theory-of-
# trading/system-wide-audit-and-design/reverse-engineering/
# 03-poller-and-state-schema.md Part A) -- same "real, complete,
# nothing ever invoked it" gap as every worker above until it's added
# here. Drives the whole live-decision loop (candle close -> state
# tracker -> live_decision_agent -> LiveScheduler's target_weights,
# point 7 option 1) end to end; without this line the loop never runs
# in a real deployment, only in tests.
supervise vinu-live live-decision-worker
exec vinu-live serve --host 0.0.0.0 --port 8091
