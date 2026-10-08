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

# Phase 9 scheduler-wiring (New-talk-agents/new-thinking/new-restructure/
# phases/phase-9-scheduler-wiring/): before this, vinu-agent's Dockerfile
# ran `vinu-agent serve` directly (CMD, no entrypoint script) and nothing
# ever called check_skill_edits() -- correct and tested since Phase 6, but
# with no live caller, same "wiring gap, not a design gap" shape as
# vinu-portfolio's drawdown-monitor fix and vinu-live's trade-plan-worker/
# feedback-worker/shadow-worker (see vinu-live/entrypoint.sh). Mirrored
# here: one background worker, foreground `serve` still owns the
# container's lifecycle.
# A run in flight when the previous container died is gone with its process; clear its `running` row first, before any
# worker can start a run of its own (the only moment this is safe).
vinu-agent reconcile-runs || true
supervise vinu-agent skill-audit-worker
# mermaid-explanation.md's Planner (Section 2) = a deterministic triage
# hook (agent/planner_triage_hook.py) + the real, already-built
# idea_generator (teams/research/). RunLogTrigger/ChangeGate (Phase 0)
# were correct and tested since Phase 0 but had no scheduled caller.
supervise vinu-agent planner-worker
# Significance Triage (Phase 7) delivery -- Telegram/Discord are
# independently gated on TELEGRAM_TOKEN/DISCORD_TOKEN +
# VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID/VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID
# being set in .env; flags are still recorded (just not delivered
# anywhere) if neither is configured.
supervise vinu-agent significance-worker
# Shortcoming #1 (implementation-plan task 01): capital_allocator was
# fully wired and correct when invoked but had no scheduled caller --
# approved PEND candidates could sit unfunded indefinitely. Same shape as
# the workers above: background loop, cadence/budget configurable via
# VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL / VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET.
supervise vinu-agent capital-allocator-worker
# G1 (ats-status-and-next-steps.md:92): risk_gatekeeper had no worker --
# a real research PASS parked at BENCHING forever because nothing ever
# invoked the risk_gatekeeper team. Same 90s cadence shape as
# capital-allocator: poll BENCHING/MONITORING batch and hand each to the
# real risk_gatekeeper team.
supervise vinu-agent risk-gatekeeper-worker
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
# ON. Only a strategy that passed research and simulation (an ACTIVE artifact) may trade. It was switched off for paper
# trading so unvalidated live-decision strategies could trade, which let 15-minute and 1-hour versions through that the
# simulator shows have no edge. A live-decision strategy earns an artifact by passing the validation gate, not by
# turning this guard off.
require_active_artifact: true
require_market_open: false
allowed_sessions: [premarket, regular, afterhours, overnight]
max_symbol_concentration_pct: 1.0
max_pairwise_correlation: 1.0
require_confirmation: false
allow_short: false
allow_margin: false
YAML
fi
exec vinu-agent serve --host 0.0.0.0 --port 8086
