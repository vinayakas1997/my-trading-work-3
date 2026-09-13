# Situation 20: at the exact consent-expiry instant, is the mandate expired or not?

## Question

`TradingMandate.consent_expired()` compares `(now or datetime.now(...)) >=
exp`. `>=` and `>` differ only at the exact boundary instant, which is
exactly the kind of one-character detail worth actually running rather
than assuming.

## Where

`vinu-agent/vinu_agent/broker/mandate.py::TradingMandate.consent_expired()`.

## How tested

Real `TradingMandate`, a fixed `consent_expires_at` timestamp, and three
`now` values passed directly to `consent_expired(now=...)`: exactly equal,
one microsecond before, one microsecond after.

## Observed

```
consent_expires_at == now, checked at exactly 'now': expired = True
consent_expires_at == now, checked 1 microsecond earlier: expired = False
consent_expires_at == now, checked 1 microsecond later: expired = True
```

## Verdict: matches the design, and it's the conservative choice

`>=` means the mandate is treated as expired starting at the exact
configured instant, not one tick after it -- consistent with "renew it
before it lapses" being the operator's job, and with every other fail-safe
boundary in this codebase erring toward blocking a moment early rather
than a moment late.
