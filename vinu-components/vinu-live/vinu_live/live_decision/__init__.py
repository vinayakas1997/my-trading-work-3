"""The live decision loop -- points 2-5 of missing-pieces-of-system/
new-theory-of-trading/system-wide-audit-and-design/reverse-engineering/.

Candle-close poller (poller.py) -> live indicator detector (detector.py)
-> stage/state tracker (state_tracker.py) -> hand-off to
live_decision_agent (vinu-agent, over HTTP) once a (ticker, strategy)
pair reaches ready_to_execute.
"""
