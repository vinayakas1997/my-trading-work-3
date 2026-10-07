# Situation 6: does changing the reauth-band env var at runtime do anything?

## Question

`REAUTH_BAND_FRACTION = float(os.environ.get("VINU_AGENT_GUARD_REAUTH_FRACTION", "1.0"))`
is a module-level constant in `order_guard.py`, computed once when the
module is first imported. If an operator changes that env var while the
process is already running (e.g. via a container's env-reload, or a shell
export before what they think is a live reconfigure), does the reauth band
actually change, or is this silently a boot-time-only knob?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py`, module-level
`REAUTH_BAND_FRACTION` (top of file) and its two call sites inside
`check()` (the `max_order_value` and `max_position_pct` reauth bands).

## How tested

Imported the real module, read `REAUTH_BAND_FRACTION`, then set
`os.environ["VINU_AGENT_GUARD_REAUTH_FRACTION"] = "0.5"` *after* the import
already happened (simulating an operator changing the env var without
restarting the process), then re-read the constant and ran a real order
through `check()` that would only get held for reauth if the band were
genuinely live at 0.5.

## Observed

```
REAUTH_BAND_FRACTION as already imported: 1.0
env var set to 0.5 AFTER import -- module constant now: 1.0
order at 90% of max_order_value -> allowed=False, needs_reauth=False
```

(The order was rejected outright, not held for reauth, because it was
priced at $900 against a $1000 `max_order_value` cap -- it actually exceeds
the cap, so the correct behavior at `REAUTH_BAND_FRACTION=1.0` is a flat
reject either way. The point being tested is that the constant itself never
moved off `1.0` despite the env var change.)

## Verdict: matches design, but worth documenting explicitly

Every other numeric knob in this file that's read from an env var
(`VINU_AGENT_ORDER_THROTTLE_PER_SEC`, `VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC`)
is read the same way -- once, at import/construction time -- so this isn't
an inconsistency, it's the established pattern (the module docstring even
calls this "a hard safety ceiling... belongs in the same 'restart to
change' category as the mandate's pass/fail switches"). But it's an easy
operational mistake: an operator who edits this env var on a running
container and expects the next order to see the new reauth band will be
wrong, silently, with no error or warning anywhere. Not fixed here (working
as designed), but worth flagging as a real gap between intent
("VINU_AGENT_GUARD_REAUTH_FRACTION so an operator can tighten... without a
code change") and what "without a code change" actually requires (a
process restart, not just an env var edit).
