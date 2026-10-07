# Situation 23: does my own reconciliation-drift alert spam every cycle by default?

## Question

`notification_noise.py`'s docstring states the noise gate is "permissive
by default -- every window is 0/disabled unless an operator sets the
matching `VINU_AGENT_NOTIFY_*` env var." My own earlier fix (#8,
`fixes-log.md`) wired `TradePlanOrchestrator._reconcile_book_with_broker()`
to call `/notify/reconciliation-drift` for every uncorrected phantom-
position/side-conflict finding, on every reconciliation cycle the drift
persists. With a completely default deployment (no `VINU_AGENT_NOTIFY_*`
env vars set), does an unresolved drift actually send a fresh real alert
on every single cycle, or does something still rate-limit it?

## Where

`vinu-agent/vinu_agent/agent/notification_noise.py::NotificationNoiseGate`
(`evaluate()`'s `dedup_window_sec` gate, `reserve()`'s
`reservation_ttl_sec`) + `vinu-agent/vinu_agent/server/routes_notify.py::_deliver_notification()`
+ `vinu-live/vinu_live/trade_plan/orchestrator.py`'s reconciliation loop,
run every `trade_plan_worker_interval_sec` (config default: **300
seconds**).

## How tested

Real `NotificationNoiseGate` (module-level singleton, reset between runs),
real `_deliver_notification()`, only the actual channel `send_message`
call faked (a call-counting stand-in). Called the same key 5 times
sequentially (simulating 5 reconciliation cycles finding the same
persisting drift) under default settings, then again with
`VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC=300` set.

## Observed

```
default dedup_window_sec = 0.0
default reservation_ttl_sec = 30.0
cycle 0-4 (default settings): all {'status': 'ok', 'delivered': 1, ...}
real channel sends across 5 identical sequential cycles: 5

(with VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC=300)
cycle 0: delivered
cycle 1-4: {'status': 'suppressed', 'reason': 'duplicate within 300s'}
real channel sends across 5 identical cycles: 1
```

`reserve()`'s 30-second reservation TTL does not help here either -- it's
released immediately after a successful send completes (`record_sent()`
pops it), so it only ever protects against two *genuinely concurrent*
calls racing each other, not sequential calls minutes apart.

## Verdict: matches the documented design -- and it's a real, worth-flagging default for operators

This isn't a bug in my fix: every existing notify route in this file
(`trade-plan-pending` included) shares the exact same
`_deliver_notification()` call and the exact same permissive-by-default
posture -- the noise gate's own docstring says this is intentional, so a
freshly wired route inherits the established, consistent behavior of every
sibling route rather than deviating from it. But it's worth being precise
about the real number for an operator: with the trade-plan worker's actual
default 300-second cycle interval, an unresolved reconciliation drift (a
phantom broker position nobody has investigated yet) will page every
configured channel **every 5 minutes indefinitely** on a totally default
deployment -- 288 times over an unattended day. `evaluate_config()`'s own
comment for a *different* window
(`quiet_min_severity` matching `trade_plan_worker_interval_sec`'s cadence)
shows the codebase is aware cadence matters here; an operator running this
in production should set `VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC` (or a
cooldown) deliberately for this alert type specifically, the same way
they would for any other CRITICAL-severity, cycle-driven condition. Not
changed here -- overriding just this one route's defaults would make it
inconsistent with every sibling route, which is a worse outcome than
leaving the codebase-wide policy alone and documenting the real number.
