#!/bin/bash
set -e

# Phase 9 scheduler-wiring (New-talk-agents/new-thinking/new-restructure/
# phases/phase-9-scheduler-wiring/): before this, vinu-agent's Dockerfile
# ran `vinu-agent serve` directly (CMD, no entrypoint script) and nothing
# ever called check_skill_edits() -- correct and tested since Phase 6, but
# with no live caller, same "wiring gap, not a design gap" shape as
# vinu-portfolio's drawdown-monitor fix and vinu-live's trade-plan-worker/
# feedback-worker/shadow-worker (see vinu-live/entrypoint.sh). Mirrored
# here: one background worker, foreground `serve` still owns the
# container's lifecycle.
vinu-agent skill-audit-worker &
# mermaid-explanation.md's Planner (Section 2) = a deterministic triage
# hook (agent/planner_triage_hook.py) + the real, already-built
# idea_generator (teams/research/). RunLogTrigger/ChangeGate (Phase 0)
# were correct and tested since Phase 0 but had no scheduled caller.
vinu-agent planner-worker &
# Significance Triage (Phase 7) delivery -- Telegram/Discord are
# independently gated on TELEGRAM_TOKEN/DISCORD_TOKEN +
# VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID/VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID
# being set in .env; flags are still recorded (just not delivered
# anywhere) if neither is configured.
vinu-agent significance-worker &
# Shortcoming #1 (implementation-plan task 01): capital_allocator was
# fully wired and correct when invoked but had no scheduled caller --
# approved PEND candidates could sit unfunded indefinitely. Same shape as
# the workers above: background loop, cadence/budget configurable via
# VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL / VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET.
vinu-agent capital-allocator-worker &
# G1 (ats-status-and-next-steps.md:92): risk_gatekeeper had no worker --
# a real research PASS parked at BENCHING forever because nothing ever
# invoked the risk_gatekeeper team. Same 90s cadence shape as
# capital-allocator: poll BENCHING/MONITORING batch and hand each to the
# real risk_gatekeeper team.
vinu-agent risk-gatekeeper-worker &
# ATS plumbing: ensure paper trading queue works outside market hours and
# closing longs is not blocked as "short" -- tmpfs /nonexistent is empty
# on every fresh container, so create the mandate here if none exists.
if [ ! -f /nonexistent/.vinu/mandate.yaml ]; then
  mkdir -p /nonexistent/.vinu
  cat > /nonexistent/.vinu/mandate.yaml <<'YAML'
allowed_tickers: ["*"]
blocked_tickers: []
max_position_pct: 0.25
max_order_value: 50000.0
max_daily_orders: 20
# how-to-make-it-live.md #8: portfolio-wide daily order ceiling across ALL
# symbols (max_daily_orders above is per-symbol -- 20/symbol x N symbols had
# no aggregate cap). reduce_only orders are exempt. Tune to your live symbol
# count: this 50 is a safety net for a ~3-9 symbol universe -- generous over
# realistic daily operation, but a hard stop well before a runaway
# signal fan-out or retry loop turns into hundreds of orders.
max_daily_orders_portfolio: 50
max_daily_trade_volume: 200000.0
max_capital_utilization_pct: 1.0
require_active_artifact: true
require_market_open: false
max_symbol_concentration_pct: 1.0
max_pairwise_correlation: 1.0
require_confirmation: false
allow_short: true
allow_margin: false
YAML
fi
exec vinu-agent serve --host 0.0.0.0 --port 8086
