---
name: vinu-agent
port: 8086
depends_on: [vinu-stock-price, vinu-tools, vinu-news, vinu-initial-analysis, vinu-strategy, vinu-simulator, vinu-research]
---

# vinu-agent

## What it does

LLM-driven agent/swarm orchestrator with chat sessions, a skills library
(`vinu-agent/skills/`), and a broker-execution layer (`AlpacaBroker`) that
fronts every other vinu-* service as a callable tool. This is the "brain"
that composes skills + tools + memory + governor at runtime, built out
across both audit plans.

## Scope for this E2E plan

**Mostly out of scope for Stage 1.** Stage 1 is a scripted/CLI historical
simulation (`vinu-portfolio historical-simulate`), not an agent-driven run
— it doesn't need the agent loop or LLM reasoning to produce the
backtest numbers. The broker-execution layer (`AlpacaBroker`,
`routes_broker.py`) specifically is deferred to Stage 2, per the earlier
explicit scope decision, since that's where real (paper) order placement
starts to matter.

The one part of this service that IS relevant to Stage 1: the skills
system (`agent-self`, `daily-allocation`, `live-safety` — built/updated in
the prior audit plan) documents how the agent is supposed to read and act
on `vinu-portfolio`'s daily game plan output. Stage 1's game-plan output
should be checked against those skill docs for consistency, even though
the agent isn't actually running the simulation itself.

## When it would run (Stage 2+)

Depends on nearly everything (`vinu_stock_price`, `vinu_tools`,
`vinu_news`, `vinu_initial_analysis`, `vinu_strategy`, `vinu_simulator`,
`vinu_research` — all listed in its `services` config dict), since it can
call any of them as a tool during a session.

## Where data is stored

`VINU_AGENT_DATA_ROOT` (default `~/.vinu`), with `sessions_dir` (chat
session transcripts) and `memory_dir` subdirectories. Skills are mounted
read-only from `vinu-agent/skills` (Docker: `./vinu-agent/skills:/app/vinu-agent/skills:ro`).

## Dependencies

All other vinu-* services (see `services` dict in `vinu_agent/config.py`),
plus:
- LLM provider — configurable (`VINU_LLM_PROVIDER`, default `openai`,
  model `gpt-4o-mini`) or a custom `VINU_LLM_BASE_URL`.
- `AlpacaBroker` (`vinu_agent/broker/alpaca.py`) for order execution —
  Stage 2+ only.

## API surface (relevant to Stage 2, not Stage 1)

- `POST /sessions` / `POST /sessions/{id}/messages` — chat-driven agent
  interaction.
- `POST /broker/order`, `/broker/halt`, `/broker/resume`, `/broker/account`,
  `/broker/positions` — paper/live order execution, deferred to Stage 2.

## Known gap as of this document

Broker credential wiring for `AlpacaBroker` has not been done — explicitly
deferred until Stage 2 starts, per the earlier scope decision in this
session.
