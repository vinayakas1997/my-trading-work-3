# Testing - 18-data (provider order)

Command:
- python3 -m pytest vinu-stock-price/tests/ -q -k "provider or registry or fallback"
- VINU_PROVIDER_ORDER="polygon,alpaca" python3 -c "from vinu_stock.providers.registry import FALLBACK_CHAINS; print(FALLBACK_CHAINS)"
Expected: 13 passed, env override flips chain.
Actual: 13 passed + 1 pre-existing permission error, override works.
Status: green for order, red for PIT/gap pending.
Proof log: build output 2026-09-09.
Note: PIT + gap + freeze pending separate.
