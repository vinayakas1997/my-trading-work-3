---
task: 03-significance-triage-notifications.md
status: code-verified complete (real credentials + live delivery pending — needs user)
---

# Status: task 03 — wire real notification credentials for Significance Triage

## Verification result

The task framed itself as "the cheapest fix in the whole plan — the only missing piece is
configuration, not code." Re-checked (2026-08-17): **the code path is fully live and correct, and the
failure modes are already right.** The only genuinely open items are credential provisioning (a
user/secrets decision) and a live delivery check.

## What I verified (with file:line evidence)

- Detection + delivery wiring is live:
  - `vinu-agent/vinu_agent/agent/significance_triage.py:270` — `deliver_flag()`: best-effort per
    channel, `LOG.exception` on delivery failure, **never raises** into the worker loop.
  - `vinu-agent/vinu_agent/agent/scheduler_workers.py:158` — `build_channel_targets()`: Telegram and
    Discord are independently gated on `token + id` both being set; unconfigured channels log INFO and
    are omitted (never an error, never a guess).
  - `vinu-agent/vinu_agent/agent/scheduler_workers.py:177` — `_run_detector_for_ticker()`: when a flag
    is created but `targets == []`, logs a clear WARNING ("...no channel is configured to deliver it"),
    keeps the flag stored, does not crash.
  - `vinu-agent/vinu_agent/cli.py:407` — the significance-worker path calls `build_channel_targets`.
- Missing/invalid-credentials failure mode is correct and covered by tests:
  - `test_one_channel_failing_does_not_block_the_others` (delivery failure is logged, not fatal).
  - `test_no_config_returns_no_targets` / `test_token_without_chat_id_is_not_enough` (half-configured
    channels never fire).
  - NEW `TestMissingChannelFailureMode` (added this task): a real repeated-rejection detection with
    zero configured channels still creates + stores the flag AND emits the loud "no channel is
    configured" warning — detection is never silently dropped.
- Credential documentation exists: `vinu-components/.env-example` already has a
  "Significance Triage delivery" section documenting `TELEGRAM_TOKEN`, `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`,
  `DISCORD_TOKEN`, `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID` (commented, with setup instructions), so the
  requirement is discoverable without reading code.

## What I did

- Added `vinu-agent/tests/test_significance_triage.py::TestMissingChannelFailureMode` (1 test) locking
  the missing-credentials failure mode (flag still stored, clear warning, no crash).
- Full suite: `vinu-agent/tests` **841 passed**.

## BLOCKER — needs the user (not a code decision)

1. Provision real credentials into `vinu-components/.env`: a real Telegram bot token (`@BotFather`) +
   admin chat id, and/or a Discord bot token + channel id (or a webhook transport if one is desired).
   This is a secrets/config decision the plan explicitly says an implementing agent must not guess.
2. Staging verification: trigger a real significance event (manufacture a repeated-rejection pattern) and
   confirm a message actually arrives in the configured channel.

Once credentials are supplied, the only remaining action is filling `vinu-components/.env` (values are
already read by `load_config()` — no code change needed) and running the staging check.

## Alignment with plan

- Steps 1 (read `notify_channels.py`/`build_channel_targets` for env expectations): done.
- Step 2 (confirm credentials with the owner): **pending user**.
- Step 3 (add keys to `.env`/`.env.example`): `.env.example` already documents them; `.env` provisioning
  pending user.
- Step 4 (real event → real message): **pending user** (needs live credentials).
- Step 5 (sensible missing/invalid-credential failure mode): verified + now covered by a test.