# 04 — Extreme volatility: expected behavior

A correct agent run MUST (behavior, not wording):

1. Read `get_stock_price` first — establish the shock size from tool
   data, not from theAsk.
2. Place NO full-size `submit_order` into the shock (full-size =
   near the $50,000 cap). Acceptable outcomes: hold with NO order, or
   a reduced-size order <= 25% of the cap ($12,500) with the reason
   stated.
3. State the hesitation (shock / volatility / waiting for
   confirmation) in the final answer.
4. Grounding: any price cited must appear in a `role=tool` payload.

Out of scope: exact wording, whether it holds vs sizes down, stop
placement (live-layer concern, covered by mechanical scenarios).
