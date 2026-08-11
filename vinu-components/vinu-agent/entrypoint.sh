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
exec vinu-agent serve --host 0.0.0.0 --port 8086
