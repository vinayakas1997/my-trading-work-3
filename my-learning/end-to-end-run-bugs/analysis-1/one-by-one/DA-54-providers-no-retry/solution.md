# DA-54 🟡 vinu-news providers — no retry, bypass `net.request()`

**Component:** `vinu-news`
**Files Changed:** `vinu-news/vinu_news/providers/yahoo.py`, `vinu-news/vinu_news/providers/alpaca.py`

## Problem

`yahoo.py` and `alpaca.py` made raw `requests.get()` calls with zero transient retry. They also bypassed `vinu_news.net.request()` which already has retry + Docker fallback (post-DA-53).

## Solution

Switched both providers from `requests.get()` to `vinu_news.net.request("GET", ...)` — they inherit 3x exponential backoff retry + Docker loopback fallback for free.

### Files changed

| File | Change |
|------|--------|
| `vinu-news/vinu_news/providers/yahoo.py` | `requests.get()` → `net.request("GET", ...)`, removed redundant `raise_for_status()` |
| `vinu-news/vinu_news/providers/alpaca.py` | `requests.get()` → `net.request("GET", ...)`, removed redundant `raise_for_status()` |

### Verification

1. `python -c "import ast; ast.parse(open('.../yahoo.py').read()); print('OK')"` ✓
2. `python -c "import ast; ast.parse(open('.../alpaca.py').read()); print('OK')"` ✓
3. `from vinu_news.providers.yahoo import YahooTickerNewsProvider` ✓
4. `from vinu_news.providers.alpaca import AlpacaTickerNewsProvider` ✓
