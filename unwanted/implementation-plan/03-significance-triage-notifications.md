---
name: significance-triage-notifications
closes: shortcoming #4 in ../01-vinu-components-shortcomings.md
status: code-verified complete — real credentials + live-delivery verification pending (needs user)
---

# Task: wire real notification credentials for Significance Triage

## Goal

Supply real Telegram and/or Discord credentials so Significance Triage's already-working detection code
actually reaches a human, instead of firing into a void.

## Why

This is the cheapest fix in the whole plan. The code path is fully live and correct —
`vinu-agent/vinu_agent/agent/significance_triage.py` has three real pattern detectors
(`detect_repeated_rejection_pattern`, `detect_large_funding_pattern`, `detect_thesis_contradiction_pattern`),
and `notify_channels.py` / `build_channel_targets` know how to deliver a message. The only missing piece
is configuration, not code.

## Current state (verified 2026-08-17 — re-check before building)

- `significance-worker` is already started by `vinu-agent/entrypoint.sh` and runs continuously via
  `cli.py`'s `run_significance_cycle`.
- `notify_channels.py` and `build_channel_targets` exist and are called from the significance-worker
  path.
- No Telegram or Discord credentials were found configured in `.env` at audit time — confirm this is
  still true (check `.env`, `.env.example`, and wherever `vinu-agent`'s config loader reads secrets from).

## Steps

1. Read `notify_channels.py` and `build_channel_targets` to determine exactly which env vars / config
   keys they expect (bot token, chat ID / channel ID, webhook URL — whichever transport is implemented).
2. Confirm with whoever owns the actual Telegram bot / Discord server which credentials to use — this is
   a config/secrets decision, not a code decision, and shouldn't be guessed at by an implementing agent.
3. Add the required keys to `.env` (and `.env.example` with placeholder values, so the requirement is
   discoverable without reading the code).
4. Trigger a real significance event in a test/staging environment (e.g. manufacture a repeated-rejection
   pattern) and confirm a message actually arrives in the configured channel.
5. Confirm the failure mode is sensible if credentials are missing or invalid — the significance-worker
   should log the delivery failure clearly, not silently drop the detection or crash the worker loop.

## Acceptance criteria

- A real significance-triage detection results in a real message delivered to a real Telegram/Discord
  channel, verified manually or via a staging-environment test.
- Missing/invalid credentials produce a clear log message, not a silent failure or worker crash.
- `.env.example` documents the required keys.

## Dependencies

None. This is the fastest task in the plan — do it any time, independent of ordering.
