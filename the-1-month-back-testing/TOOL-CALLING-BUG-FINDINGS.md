# Tool-Calling Bug — What Was Wrong, How to Check, How to Re-run

**Date:** 2026-08-03
**Status:** Fixed and individually verified. Full end-to-end smoke test NOT yet re-run (stopped before completion — see "How to re-run" below).

## What was wrong (found via the 20-day replay's $0 P&L result)

The 20-day agentic replay (`results/run-2026-07-06-2026-07-31/`) showed the
agent never placing a single trade. The original conclusion was "the local
`qwen36-35B` model can't reliably do tool-calling." **That conclusion was
wrong, or at least incomplete.** The real root cause was found in
`vinu-agent`'s own code, in two layers:

### Bug 1 (the big one) — malformed tool schemas, 26 of 29 tools

`BaseTool.to_openai_schema()` (`vinu_agent/agent/tools.py:20-28`) sends each
tool's `parameters` attribute straight to the LLM as JSON Schema, no
validation. Most tools defined `parameters` as a flat dict like
`{"symbol": {"type": "string", ...}}` — **missing the required wrapper**
(`"type": "object"`, `"properties": {...}`, `"required": [...]}`). Only 3
tools (`compact`, `factor_analysis`, `factor_backtest`) had it right.

**Proof it was the real cause, not the model:** in the same session, on the
same turn, the model called the 3 well-formed tools with perfectly correct
arguments, and every malformed tool (`get_stock_price`, `submit_order`,
`get_news`, etc.) with empty `{}` arguments — every single time, all month.
It also compounded a second way: `context.py::_format_tool_descriptions()`
reads `parameters.get("properties", {})` to build the tool list in the
system prompt — for malformed tools this returned empty, so the model's own
prompt never told it these tools *had* parameters at all.

**Fix:** rewrote `parameters` on all 26 broken tool files (29 tool classes
total — 3 files have 2 classes each) to proper JSON Schema, with `required`
inferred from each tool's own `execute()` method (`kwargs["x"]` = required,
`kwargs.get("x", ...)` = optional).

### Bug 2 — wrong URLs / missing route prefixes, found only after Bug 1 was fixed

Fixing Bug 1 let the model actually call tools with real arguments for the
first time — which immediately surfaced bugs that were previously masked
because execution never got that far:

| Tool | Was calling | Real route | Fix |
|---|---|---|---|
| `get_news` | `{url}/ticker/{symbol}` | `{url}/news/ticker/{symbol}` | added `/news` prefix |
| `get_stock_price` | `{url}/candles/{symbol}` | `{url}/stock/candles/{symbol}` | added `/stock` prefix |
| `get_features` | `{url}/requests` | `{url}/features/requests` | added `/features` prefix |
| `get_correlation` | `POST {url}/correlation/compute` (route doesn't exist) | `GET {url}/analysis/correlation/{ticker}?from_ts=&to_ts=` | rewrote to correct method/path/params |
| `get_fundamentals` | crashed: `No module named 'yfinance'` | — | added `yfinance>=0.2` to `vinu-agent/pyproject.toml` |

## Files changed (all in `vinu-components/vinu-agent/`)

- `vinu_agent/tools/*.py` — 26 files, schema wrapping (Bug 1). Also:
  `news_tool.py`, `stock_price_tool.py`, `features_tool.py`,
  `correlation_tool.py` (Bug 2 URL/route fixes).
- `pyproject.toml` — added `yfinance>=0.2`.
- `agent-api` container was rebuilt twice (`docker compose up -d --build agent-api`) to pick up both rounds of fixes.

## How to check this is actually fixed (fast, no LLM needed)

```bash
cd vinu-components
# 1) Confirm every tool now produces valid JSON Schema (should print "0 still malformed")
docker compose exec -T agent-api python3 -c "
from vinu_agent.tools import _discover_subclasses
bad = 0
for cls in _discover_subclasses():
    p = cls().to_openai_schema()['function']['parameters']
    if p.get('type') != 'object' or 'properties' not in p or 'required' not in p:
        bad += 1
        print('MALFORMED:', cls.__name__)
print(bad, 'still malformed')
"

# 2) Confirm each fixed URL actually resolves (should all print 200)
docker compose exec -T agent-api python3 -c "
import httpx, os
n = os.environ.get('VINU_NEWS_API_URL', 'http://news-api:8080')
print('news:', httpx.get(f'{n}/news/ticker/AAPL', params={'limit':3}, timeout=30).status_code)
s = os.environ.get('VINU_STOCK_PRICE_API_URL', 'http://stock-api:8081')
print('stock:', httpx.get(f'{s}/stock/candles/AAPL', params={'from':1751760000,'to':1752192000,'interval':'1D'}, timeout=30).status_code)
a = os.environ.get('VINU_INITIAL_ANALYSIS_API_URL', 'http://initial-analysis-api:8083')
print('correlation:', httpx.get(f'{a}/analysis/correlation/AAPL', params={'from_ts':1751760000,'to_ts':1752192000}, timeout=30).status_code)
import yfinance
print('yfinance: import OK')
"
```

All 4 of these were run and passed once already (2026-08-03) — this is just
the fast re-check if anything seems off later.

## How to re-run the actual agent smoke test (needs the local LLM, slow — ~9 min for 1 day)

A 1-day test already ran successfully with **Bug 1 only** fixed (confirmed
the model now passes real arguments, e.g. `get_stock_price({"symbol":"AAPL",...})`
instead of `{}`) — that run is at
`results/schema-fix-smoke-test/2026-07-06/`. A second 1-day run with
**both bugs fixed** was started but interrupted before finishing — rerun it
to get the first clean result:

```bash
cd vinu-components
docker compose up -d --build agent-api   # only needed if you've changed code since the last rebuild
cd ..
python vinu-components/vinu-agent/scripts/run_month_replay.py \
  --start 2026-07-06 --end 2026-07-06 \
  --run-id schema-and-url-fix-smoke-test
```

Check the result:
```bash
cat the-1-month-back-testing/results/schema-and-url-fix-smoke-test/2026-07-06/response.json
cat the-1-month-back-testing/results/schema-and-url-fix-smoke-test/2026-07-06/thinking.json   # full trace if response looks off
```

**If that 1-day run looks healthy** (real tool calls, real data back, a
real decision — trade or explicit no-trade reasoning, not stuck in an error
loop), re-run the full month for a real P&L number:

```bash
python vinu-components/vinu-agent/scripts/run_month_replay.py \
  --start 2026-07-06 --end 2026-07-31 \
  --run-id run-2026-07-06-2026-07-31-v2
```

This takes a long time (up to 30 min/day × 20 days) — run it in the
background, don't wait on it interactively. It's resumable: if interrupted,
re-run the same command with the same `--run-id` and it skips days that
already have a `response.json`.

## Note on scope

These are genuine `vinu-agent` production fixes, not replay-only — they
also fix `submit_order`/`get_stock_price`/etc. for real live/paper trading
sessions (relevant to Monday 2026-08-03's market open, not just this
backtest).
