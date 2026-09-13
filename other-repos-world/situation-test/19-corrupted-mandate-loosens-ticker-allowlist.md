# Situation 19: does a corrupted mandate.yaml loosen or tighten trading restrictions?

## Question

`TradingMandate.load()` catches any exception while reading `mandate.yaml`
and falls back to `cls(**SETTINGS.overrides())` -- the dataclass's bare
defaults. That's clearly correct for "no mandate.yaml exists yet" (a
different, earlier branch). But if a real, already-configured mandate file
(with a deliberately restricted `allowed_tickers`) becomes unparseable --
a bad manual edit, a partial write, disk corruption -- does the same
fallback silently discard the operator's real restriction and replace it
with the maximally permissive default (`allowed_tickers: {"*"}`, every
ticker allowed)?

## Where

`vinu-agent/vinu_agent/broker/mandate.py::TradingMandate.load()`'s
`except Exception as exc:` block.

## How tested

Real `TradingMandate.load()`, real files. First loaded a real, valid
mandate file restricting `allowed_tickers` to two symbols; then corrupted
the same file's content (invalid YAML) and loaded it again.

```python
good_mandate = TradingMandate.load(good_path)   # allowed_tickers: [AAPL, MSFT]
bad_mandate = TradingMandate.load(bad_path)     # same file, now corrupted
```

## Observed (before the fix)

```
real operator config: allowed_tickers = ['AAPL', 'MSFT']
SAME operator's config file, now corrupted: allowed_tickers = ['*']
'*' in fallback allowed_tickers (means EVERY ticker allowed): True
fallback require_active_artifact = True (operator's real config had this OFF: False)
```

Every *other* field in this dataclass defaults to the strictest option
(`require_active_artifact=True`, `require_market_open=True`,
`require_confirmation=True`, `allow_short=False`, `allow_margin=False`) --
`allowed_tickers` defaulting to `{"*"}` is the one exception, and it's a
reasonable default for "nothing has ever been configured." It is not a
reasonable thing to silently fall back to when a real, working
restriction existed a moment ago and merely became unreadable.

## Verdict: real bug, fixed

**Fixed**: on a parse failure (file exists but can't be read), `load()`
now returns `cls(allowed_tickers=set(), **SETTINGS.overrides())` --
blocking every symbol from new/increasing orders -- instead of the
permissive `{"*"}` default, and logs at `ERROR` (not `WARNING`) since this
is a much more urgent, actionable state than "no mandate configured yet."

This fix only became safe to make after fixing situation 22 first (below):
without that companion fix, an empty `allowed_tickers` would have also
blocked every `reduce_only` exit, trapping every existing position for as
long as the file stayed broken -- arguably worse than the original bug.
With situation 22's exemption in place, failing closed here blocks new
exposure without trapping anything already open.

Added `tests/test_mandate_load_fallback.py` (4 tests): a missing file
still defaults permissively (unaffected by this fix); a corrupted file
fails closed to an empty allowlist; a real restrictive config followed by
corruption never ends up wider than it started; and a `reduce_only` order
still clears the fail-closed fallback. Full `test_order_guard.py` (109
passed combined with other suites in this batch, same 2 pre-existing
`TestOrderThrottle` failures), `test_trade_tool.py`, and
`test_kill_switch.py` all still pass.
