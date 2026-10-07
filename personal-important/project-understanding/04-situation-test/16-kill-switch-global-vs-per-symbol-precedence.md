# Situation 16: does a global halt really override a per-symbol resume, and vice versa?

## Question

`kill_switch.py::is_trading_halted()`'s docstring states "a global halt
always takes precedence over a scoped halt." Two concrete scenarios worth
actually running rather than trusting the docstring: (a) if someone
`resume_trading(scope="AAPL")`s one symbol while a *global* halt is active,
does AAPL actually stay halted? (b) if a symbol has its own independent
halt (unrelated to any global event) and a global halt is later resumed,
does the symbol's own halt survive, or does the global resume wipe it out
too?

## Where

`vinu-agent/vinu_agent/broker/kill_switch.py::halt_trading()` /
`resume_trading()` / `is_trading_halted()`.

## How tested

Real filesystem kill switch, no mocks -- actual halt marker files under
`/tmp/vinu-trading-halt*`.

```python
kill_switch.halt_trading(scope=None)              # global halt
kill_switch.resume_trading(scope="AAPL")           # try to resume just AAPL
kill_switch.is_trading_halted("AAPL")              # still halted?

kill_switch.halt_trading(scope="MSFT")             # independent per-symbol halt
kill_switch.halt_trading(scope=None)               # now ALSO a global halt
kill_switch.resume_trading(scope=None)             # global resume only
kill_switch.is_trading_halted("MSFT")              # still halted?
```

## Observed

```
Part A -- global halt + resume_trading(scope="AAPL"):
  AAPL halted? True   MSFT halted? True   (before the scoped resume)
  after resume_trading(scope="AAPL") during the GLOBAL halt:
    AAPL halted? True   (unchanged -- global still wins)
    MSFT halted? True
  after the GLOBAL resume: AAPL halted? False   MSFT halted? False

Part B -- independent per-symbol halt survives an unrelated global resume:
  both active: AAPL halted? True   MSFT halted? True
  after GLOBAL resume only (MSFT's own halt untouched):
    AAPL halted? False
    MSFT halted? True   -- correct, its own halt is a separate marker file
```

## Verdict: matches the documented design, confirmed on the real filesystem

Both directions hold: a scoped resume can't punch a hole through an active
global halt (attempting to "resume" AAPL while globally halted is a no-op
for AAPL specifically -- it only deletes AAPL's own, already-nonexistent,
per-symbol marker), and a global halt lifting doesn't collaterally clear an
unrelated symbol's own separate halt marker. This matters operationally: an
operator investigating one bad symbol (per-symbol halt) and separately
hitting the global kill switch for an unrelated reason (e.g. a drawdown
breaker) can resolve the global event without accidentally re-enabling
trading on the symbol they're still investigating.
