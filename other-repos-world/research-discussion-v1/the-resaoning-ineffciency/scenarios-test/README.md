# scenarios-test

Expanded pre-live mechanical scenarios (no LLM) -- the follow-on to
`tests/test_pre_live_scenarios.py`'s original 3. Patterns discussed,
not yet built:

- Gap-down crash (does the catastrophic backstop actually catch it, not
  just the invalidation rule?)
- Sideways chop (proves the system does nothing -- no phantom entries on
  noise)
- Multiple correlated positions moving together (does the
  correlation/concentration overlay actually kick in?)
- Broker outage mid-cycle (entries pause, but does an exit still fire?)
- Kill switch engaged mid-cycle (blocks a would-be entry, still lets a
  reduce-only exit through?)

Awaiting direction on which to build first.
