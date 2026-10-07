# Situation 25: does a small, clean, guard-approved order ever auto-execute by default?

## Question

`TradeTool.execute()`'s final gate before actually submitting is `if
needs_reauth or mandate.require_confirmation:` -- and `require_confirmation`
defaults to `True` in the mandate dataclass, unconditionally, with no size
or risk threshold anywhere in that check. Does that mean literally *every*
order -- even a trivial, clearly-safe one that clears every other check --
gets held for human confirmation on a default deployment, or is there some
other path that lets small orders through automatically?

## Where

`vinu-agent/vinu_agent/tools/trade_tool.py::TradeTool.execute()`, the
`if needs_reauth or mandate.require_confirmation:` block (unconditional on
the second half) + `vinu-agent/vinu_agent/broker/mandate.py`'s
`require_confirmation: bool = True` default.

## How tested

Real `TradeTool.execute()`, real `TradingMandate.load()` (no mandate.yaml
present on this machine, so genuine dataclass defaults, not a mocked
mandate), only the broker and `OrderGuard` mocked at the network/decision
boundary -- and the guard mock returns an unconditional approval, so
nothing about the order itself is being rejected. A $1 order, 1 share.

## Observed

```json
{
  "status": "pending_confirmation",
  "message": "Awaiting user confirmation before executing order",
  "reason_code": null,
  ...
  "mandate": {"require_confirmation": true, ...}
}
```

Held for confirmation despite being trivially small and fully
guard-approved.

## Verdict: matches the design, and worth stating precisely for anyone deploying this

Not a bug -- this is a deliberate, human-in-the-loop-by-default posture,
consistent with every other default in `TradingMandate`
(`require_active_artifact=True`, `require_market_open=True`,
`allow_short=False` are all the strictest option; situation 19 found
`allowed_tickers`'s permissive default was the one deliberate exception,
justified there by "nothing has been configured yet"). But it's easy to
miss exactly how absolute this one is while reading the code, because
almost every test and ad-hoc script written *during* this audit
(situations 4, 5-14, 17, and the original #6/#8 fixes) explicitly sets
`require_confirmation=False` on a mocked mandate to get past this gate and
exercise what's underneath it -- which means an operator reading those
tests, or this codebase's own test suite in general, could reasonably come
away thinking small orders execute automatically by default. They don't:
on a fresh deployment with no mandate.yaml written yet, *every single
order* -- regardless of size, symbol, or how cleanly it clears every
guard check -- is held for an explicit confirmation step. `require_confirmation:
false` in `mandate.yaml` is a deliberate, single-line opt-out an operator
must make consciously; nothing in the shipped defaults executes an order
autonomously.
