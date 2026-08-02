---
name: options-greeks-tool
component: vinu-agent
status: not-started
---

# Item 4 — Live Options Greeks / IV Tool

## What this is

A new `vinu-agent` tool giving the LLM on-demand access to live options
data (Greeks + implied volatility) for a symbol, via Alpaca's option
chain endpoint. This is **not** a `vinu-initial-analysis` angle — it
cannot be, because Alpaca's Greeks/IV data is a live snapshot only
(today's data, no historical lookup at all), which doesn't fit the
batch/backfill pattern every angle uses (`compute(symbol, bars, news,
from_ts, to_ts, ...)`  — an angle is expected to answer questions over a
historical range; this data source structurally cannot). It belongs in
`vinu-agent` as a live tool, same architectural slot as
`fundamentals_tool.py`.

## Data source specifics — confirmed via Alpaca's own docs, 2026-08-02

- Option chain endpoint: `https://data.alpaca.markets/v1beta1/options/...`
  — check `docs.alpaca.markets/reference/optionchain` for the exact path
  before implementing (this plan doesn't guess the full path; verify it
  live against the account's actual API access before writing code).
- Returns, per contract: latest trade, latest quote, **implied volatility
  and all five Greeks (delta, gamma, theta, vega, rho), pre-computed —
  no extra parameter needed to get them.**
- **This is a live snapshot only.** No historical lookup on this specific
  endpoint. Separate historical option bars exist
  (`https://data.alpaca.markets/v1beta1/options/bars`) but only **since
  February 2024** — don't build a historical-backfill path against this;
  it cannot reach the 2022 Stage 1 start date and isn't what this tool is
  for anyway (the tool is for "what does the options market think right
  now," not backtesting).
- Uses the same Alpaca API credentials already in `vinu-components/.env`
  (`ALPACA_API_KEY`/`ALPACA_API_SECRET`) — this is the same account
  already used for stock market data and (per item 3's findings) already
  working for paper trading. No new credential needed.

## Pattern to follow — copy `fundamentals_tool.py`'s shape exactly

Read `vinu-components/vinu-agent/vinu_agent/tools/fundamentals_tool.py`
in full first. Key structural points to replicate:
- Subclass `BaseTool` (`vinu_agent/agent/tools.py`) — `name`,
  `description`, `parameters` (JSON-schema-shaped dict for the LLM's
  function-calling interface), `execute(self, **kwargs) -> str` returning
  a JSON string.
- **No manual registration needed.** `vinu_agent/tools/__init__.py`'s
  `_discover_subclasses()` auto-imports every module in the `tools/`
  package and finds every `BaseTool` subclass via `__subclasses__()`.
  Drop the new file in `vinu_agent/tools/`, it's live automatically.
- `fundamentals_tool.py` uses `yfinance` because that's the only source
  for fundamentals in this stack. This tool should use `requests` against
  Alpaca's endpoint directly (matching `vinu_agent/broker/alpaca.py`'s
  own pattern of a plain `requests.Session()` with the API key/secret
  headers — `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY`), not a new SDK
  dependency, to stay consistent with how the rest of `vinu-agent`
  already talks to Alpaca.

## Files to touch

- New: `vinu-components/vinu-agent/vinu_agent/tools/options_tool.py`
- Reference only: `vinu_agent/tools/fundamentals_tool.py` (structural
  pattern), `vinu_agent/broker/alpaca.py` (Alpaca auth/request pattern —
  note this file uses the **trading** API base URL
  `paper-api.alpaca.markets`; the options data endpoint is on the
  **market data** base URL `data.alpaca.markets`, already used by
  `vinu-stock-price`/`vinu-news` — check
  `ALPACA_DATA_BASE_URL` in `.env`, don't hardcode a new one).
- If the tool needs registration-time config (API base URL), follow the
  `os.environ.get(...)` module-level pattern already used in
  `broker/alpaca.py` lines 15-22, reading `ALPACA_DATA_BASE_URL` and the
  existing `ALPACA_API_KEY`/`ALPACA_API_SECRET`.

## Suggested tool shape (for whoever implements — not prescriptive on every field)

```python
class OptionsGreeksTool(BaseTool):
    name = "get_options_greeks"
    description = "Fetch live options chain data for a symbol: Greeks (delta, gamma, theta, vega, rho) and implied volatility, per contract. Live snapshot only — cannot answer historical questions."
    parameters = {
        "symbol": {"type": "string", "description": "Underlying stock symbol (e.g., AAPL)"},
        "expiration": {"type": "string", "description": "Optional: filter to a specific expiration date (YYYY-MM-DD)"},
    }
```

## Expected output / how to verify

- Call the tool directly (not through the LLM loop, for a first
  verification pass) against a real, liquid, optionable symbol (AAPL is
  already in the Stage 1 ticker set and has heavy options volume) during
  market hours.
- Confirm the response actually contains non-null Greeks and IV for at
  least a few contracts near the money — a response with all nulls
  suggests the API call succeeded but something about auth or path is
  wrong, not that the option genuinely has no Greeks.
- Confirm a clean, honest error (not a crash) when called for a symbol
  with no listed options, or outside market hours if the endpoint
  requires it — check what Alpaca actually returns in that case rather
  than assuming.
- Once verified standalone, confirm the LLM can actually invoke it via a
  real `vinu-agent` chat session (`POST /agent/sessions`,
  `POST /agent/sessions/{id}/messages`) with a prompt that should
  naturally trigger the tool (e.g. "what's the implied volatility on
  AAPL right now") — a tool that works when called directly but that the
  LLM never actually invokes (bad description, unclear parameters) is
  not actually done.
