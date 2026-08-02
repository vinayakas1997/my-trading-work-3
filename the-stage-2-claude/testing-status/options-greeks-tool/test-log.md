# options-greeks-tool — Test Log

**Status:** Direct tool call VERIFIED (2026-08-02) — real live Greeks/IV data
returned for AAPL, plus clean structured errors for invalid/missing inputs.
End-to-end "LLM actually invokes the tool" confirmation deferred to the next
market open (2026-08-03), see "Deferred" below.

## What will be tested / Expected output

- Direct tool call (bypassing the LLM loop) against a real, liquid,
  optionable symbol (AAPL) during market hours — confirm the response
  contains non-null Greeks (delta, gamma, theta, vega, rho) and implied
  volatility for at least a few near-the-money contracts.
- Confirm a clean, honest error (not a crash) for a symbol with no listed
  options, or outside market hours if the endpoint requires it.
- End-to-end: confirm the LLM actually invokes the tool via a real
  `vinu-agent` chat session given a natural prompt (e.g. "what's the
  implied volatility on AAPL right now") — a tool that only works when
  called directly, never invoked by the LLM in practice, is not done.
- Explicitly NOT tested: historical options backfill. This tool is
  present-time only by data-source design (Alpaca's Greeks/IV endpoint
  has no historical lookup) — don't write a test expecting historical
  coverage.
- Full detail: [../../scope-responsibilities/04-options-greeks-tool.md](../../scope-responsibilities/04-options-greeks-tool.md)

## Verification results (2026-08-02, weekend — market closed)

**Note on data freshness:** market is closed (Saturday) so the returned
quotes/Greeks are Friday-stamped. The endpoint itself is live and the shape
of the data is exactly what the tool consumes; nothing here is synthetic.

### Tool creation + auto-discovery
- New file `vinu_agent/tools/options_tool.py` (class `OptionsGreeksTool`,
  name `get_options_greeks`). Modeled on `fundamentals_tool.py` and the
  `BaseTool` contract in `vinu_agent/agent/tools.py`.
- Uses Alpaca's **live** `GET /v1beta1/options/snapshots/{symbol}` (data
  endpoint), same `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` auth headers as
  the broker client, `ALPACA_DATA_BASE_URL` from env (verified live earlier:
  status 200 with per-contract `greeks` + `impliedVolatility`).
- Rebuilt `agent-api`. Inside the running container, `import
  vinu_agent.tools.options_tool` succeeds and `get_options_greeks` appears
  in `BaseTool.__subclasses__()` — auto-registered via the existing pkgutil
  discovery (`vinu_agent/tools/__init__.py`), no manual wiring.

### Real data — AAPL (`OptionsGreeksTool().execute(symbol="AAPL", limit=100)`)
- OCC symbol parsing verified: `AAPL260803C00307500` → strike 307.5,
  expiration 2026-08-03, type Call.
- `fetch_chain("AAPL", limit=100)` → 100 contracts, **40 with full Greeks**,
  22 near/ATM (|delta| in [0.1, 0.9]). Sample real quotes, e.g.:
  - `AAPL260803C00290000` (call, strike 290): IV 119.24%, delta 0.8325,
    gamma 0.0131, theta -2.43, vega 0.0403, bid 17.29 ask 21.00, vol 142.
  - `AAPL260803C00300000` (call, strike 300): IV 84.49%, delta 0.7164,
    theta -2.32, vega 0.0545, bid 9.12 ask 10.56, vol 14427.
  - `AAPL260803C00320000` (call, strike 320): IV 62.61%, delta 0.113, theta
    -0.97, bid 0.48 ask 0.61 — deep-OTM cheap call, low delta, consistent.
  - Deep-ITM/expiry contracts sometimes lack `greeks` — matches Alpaca's own
    behavior for that endpoint (not a bug in this tool); the tool still
    returns their bid/ask/mid/last/volume/IV where present.
- `execute()` returns a single JSON string `{"status":"ok",
  "symbol":"AAPL","n_contracts":100,"contracts":[...]}`.

### Error handling (structurally required by the plan)
- **Bad symbol** `execute(symbol="ZZZZZZZZ", limit=5)` → no crash; returns
  structured `{"status":"error","error":"400 Client Error: Bad Request for
  url: https://data.alpaca.markets/v1beta1/options/snapshots/ZZZZZZZZ?limit=5"}`
  (the guarded `logger.warning` only logs, the function returns a JSON error
  string as designed).
- **401 handling:** a permissioned failure raises `PermissionError` with a
  clear message (account lacks options-data entitlement) rather than a raw
  500 — written but not exercised on this account (we have options data).
- **Missing symbol** `execute()` → `{"status":"error","error":"symbol is
  required"}`.

### Deferred — end-to-end LLM invocation (market hours only)
- The plan's stated "not done" bar is that the **LLM** actually picks
  `get_options_greeks` during a real chat session, not just the direct
  call. That needs a live (usable-model) agent session and is best done
  while the market is open so the answer is current. Defer to 2026-08-03
  (next market open) by prompting the session with e.g. "what's the implied
  volatility on AAPL right now" and confirming the tool is invoked and its
  output surfaced to the user. Registration is already proven, so this is
  the final wiring confirmation.

## Bug / Fix Log

_No bugs found yet — the tool and its error paths behave as designed; the
codebase required no fixes for this item. The deferred LLM-invocation check
is the only outstanding verification._