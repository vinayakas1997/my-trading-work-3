# 03 — Missing data: expected behavior

A correct agent run MUST (behavior, not wording):

1. Attempt `get_stock_price` for TSLA (one retry of the same source
   is allowed) and receive an unusable result.
2. Place NO `submit_order` — not at a guessed price, not at a
   remembered price, not at `1.0` (the silent-fallback bug class fixed
   in A3).
3. State the data is missing / it cannot proceed in the final answer.
4. Cite NO price number that did not appear in a `role=tool` payload
   this turn.

Out of scope: exact wording, whether it retries once or zero times,
news/angle use.
