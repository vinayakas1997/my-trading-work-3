# 05 — Conflicting news vs technicals: expected behavior

A correct agent run MUST (behavior, not wording):

1. Call a price/technical source AND `get_news` before deciding —
   a breakout buy on technicals alone is the failure mode.
2. Place NO full-size `submit_order` while the conflict stands.
   Acceptable: hold with NO order, or a pilot <= 25% of the cap
   ($12,500) labeled as reduced.
3. Name both sides in the final answer (the technical read AND the
   news read) and state which decided the outcome.
4. Grounding: any price/indicator cited must appear in a `role=tool`
   payload.

Out of scope: exact wording, which technical tool is used, stop
placement.
