# Decision — Row 9 Significance Triage delivery (manual gate 2026-09-07)

> `04:368` code complete, needs `TELEGRAM_TOKEN`/`VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID` + `DISCORD_TOKEN`/`VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID`.

## Status

- Detection + FlagStore + `deliver_flag` wired (`scheduler_workers.py:158` build_channel_targets). Delivery proven only when real credentials present and message observed arriving.
- Gate: go-live requires at least one observed Telegram or Discord delivery, not just code path. Until then `significance-worker` still records flags (no data loss).

## Dated

- 2026-09-07 — operator must provide creds before gate.
