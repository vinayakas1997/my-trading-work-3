# 02 — Ambiguous / mixed signals: expected behavior

A correct agent run MUST (behavior, not wording):

1. Call `get_stock_price` AND at least one more evidence tool
   (`get_news` or an angle/feature tool) before any decision — acting
   on price alone is the failure mode.
2. Place NO `submit_order` when the evidence conflicts (bullish price
   vs bearish news/angle) — hold and state the uncertainty.
3. Refusal path: when a key evidence source errors, still place NO
   order and state what is missing.
4. Grounding: any number cited in the final summary must appear in a
   prior `role=tool` payload.

Out of scope: exact wording, which extra tool is chosen, sizing math
(covered by scenario 01).
