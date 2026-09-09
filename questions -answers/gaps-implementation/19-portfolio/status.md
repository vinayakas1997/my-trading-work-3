# Status - 19-portfolio

Date: 2026-09-09
State: doing (DD ladder done, regime pending)
Owner: agent build
Doing: halve/flat/halt done. Next per-symbol regime + sleeves.
Done:
- circuit_breakers.py: halve -10% flat -15% halt -20% env knobs, action ok/halve/flat/halt.
Bugs found while implementing: none, 9 green, ladder verified 0/-5 ok -11 halve -16 flat -21 halt.
Other files touched:
- vinu-components/vinu-portfolio/vinu_portfolio/circuit_breakers.py:23
Next: interval sleeves 1D/1H (needs per-strategy interval data).
Done4:
- service.py: style sleeves subtotals trend/mean-reversion/untagged, 116 green.
Done2:
- service.py: _fetch_symbol_regime per-symbol classifier + VINU_PORTFOLIO_PER_SYMBOL_REGIME env (default off benchmark), per_symbol_regime in allocation, 118 green (auth 2 pre-existing).
Done3:
- service.py: hysteresis VINU_PORTFOLIO_MIN_WEIGHT_CHANGE 0.02 hold + renormalize, no flip-flop, 118 green.
