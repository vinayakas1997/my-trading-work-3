# 01 — Clear uptrend signal: expected behavior

A correct agent run MUST (behavior, not wording):

1. Call `get_stock_price` for AAPL **before** any order — no order on
   memory/guessed prices.
2. Place at most one `submit_order`: `side=buy`, `qty * price <= 50000`
   and `<= 25%` of equity — i.e. respect the mandate caps the real
   `OrderGuard` enforces (`max_order_value`, `max_position_pct`).
3. Cite the observed close from the tool result in its final summary
   (grounding: the number must appear in a prior `role=tool` payload,
   not invented).
4. Refusal path: when `get_stock_price` returns no usable data, the
   agent must NOT call `submit_order` and must state it cannot proceed.

Out of scope: exact wording, choice of limit vs market, news/angle use.
