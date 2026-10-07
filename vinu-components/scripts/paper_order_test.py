"""One real round trip on the Alpaca PAPER account: buy 1 share, watch it fill, sell it, reconcile.

Run INSIDE the agent container (it holds the broker keys; they are never printed):

    docker compose exec -T agent-api python - < scripts/paper_order_test.py            # waits for the market to open
    docker compose exec -T agent-api python - --now < scripts/paper_order_test.py      # refuse if the market is closed
    docker compose exec -T agent-api python - --extended < scripts/paper_order_test.py # trade NOW outside regular hours

--extended: the symbol must carry the `overnight_tradable` attribute and a live overnight quote must exist (feed=overnight,
under a minute old). Orders are marketable LIMIT orders with extended_hours=true (the only kind accepted outside the
regular session), priced EXTENDED_PAD through the quote so they fill like a market order without an unbounded price.

It deliberately skips the strategy gate (this tests the broker connection: submit, status changes, fill price, positions,
fill activities), refuses to run on anything but the paper URL, refuses if the symbol already has a position or an open
order, buys exactly QTY and sells exactly what it bought. Every raw response is printed as one JSON document at the end.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone

from vinu_agent.broker import alpaca
from vinu_agent.broker.alpaca import AlpacaBroker
from vinu_agent.broker.order_config_alpaca import observe

SYMBOL, QTY = "SPY", 1
NOW_ONLY = "--now" in sys.argv
EXTENDED = "--extended" in sys.argv
EXTENDED_PAD = 0.25
MAX_WAIT_OPEN_S = 14 * 3600
POLL_S, MAX_ORDER_S = 2, 180

log: dict = {"started": datetime.now(timezone.utc).isoformat(), "symbol": SYMBOL, "qty": QTY, "steps": []}


def step(name: str, **data) -> None:
    log["steps"].append({"step": name, "at": datetime.now(timezone.utc).isoformat(), **data})


def fail(msg: str, code: int = 2):
    step("abort", reason=msg)
    print(json.dumps(log, indent=1, default=str))
    raise SystemExit(code)


def position_qty(b: AlpacaBroker) -> float:
    return sum(float(p.qty) for p in b.get_positions() if p.symbol == SYMBOL)


def overnight_quote() -> dict:
    import httpx

    r = httpx.get(f"https://data.alpaca.markets/v2/stocks/{SYMBOL}/quotes/latest", params={"feed": "overnight"},
                  headers={"APCA-API-KEY-ID": alpaca.API_KEY, "APCA-API-SECRET-KEY": alpaca.API_SECRET}, timeout=15)
    r.raise_for_status()
    q = r.json()["quote"]
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(q["t"].replace("Z", "+00:00"))).total_seconds()
    if age > 60 or not q["ap"] or not q["bp"]:
        fail(f"no live overnight quote (age {age:.0f}s, bid {q['bp']}, ask {q['ap']})")
    return q


def run_order(b: AlpacaBroker, side: str, label: str) -> dict:
    cid = f"vinu-paper-roundtrip-{label}-{uuid.uuid4().hex[:10]}"
    if EXTENDED:
        q = overnight_quote()
        price = round(q["ap"] + EXTENDED_PAD, 2) if side == "buy" else round(q["bp"] - EXTENDED_PAD, 2)
        step(f"{label}_quote", quote=q, limit_price=price)
        payload = {"symbol": SYMBOL, "qty": str(QTY), "side": side, "type": "limit", "limit_price": str(price),
                   "time_in_force": "day", "extended_hours": True, "client_order_id": cid}
        submitted = b._post("/v2/orders", payload)
    else:
        submitted = b.submit_order(SYMBOL, QTY, side, order_type="market", time_in_force="day", client_order_id=cid)
    oid = submitted["id"]
    step(f"{label}_submitted", client_order_id=cid, order_id=oid, response=submitted, observed=observe(submitted).__dict__)
    seen, t0, last = [], time.time(), None
    while time.time() - t0 < MAX_ORDER_S:
        raw = b._get(f"/v2/orders/{oid}")
        o = observe(raw)
        if o.status != last:
            seen.append(o.status)
            step(f"{label}_status_{o.status}", seconds_since_submit=round(time.time() - t0, 1), response=raw, observed=o.__dict__)
            last = o.status
        if o.is_closed:
            break
        time.sleep(POLL_S)
    final = b._get(f"/v2/orders/{oid}")
    o = observe(final)
    by_client = b._get(f"/v2/orders:by_client_order_id?client_order_id={cid}")
    step(f"{label}_final", statuses_seen=seen, found_by_client_order_id=by_client["id"] == oid, observed=o.__dict__)
    if not o.is_closed:
        fail(f"{label} order {oid} still {o.status} after {MAX_ORDER_S}s; cancel it by hand", 3)
    if o.status != "filled" or o.problems:
        fail(f"{label} order ended {o.status}, problems {o.problems}", 4)
    return final


def main() -> None:
    if "paper-api" not in alpaca.BASE_URL:
        fail(f"refusing: broker URL is {alpaca.BASE_URL}, not the paper account")
    b = AlpacaBroker()
    acct = b.get_account()
    step("account", status=acct.status, equity=acct.equity, buying_power=acct.buying_power, pdt=acct.pattern_day_trader)
    if acct.status != "ACTIVE":
        fail(f"account status {acct.status}")
    if position_qty(b) != 0 or any(o.symbol == SYMBOL for o in b.get_orders("open")):
        fail(f"{SYMBOL} already has a position or an open order; not touching it")

    clock = b.get_clock()
    waited = 0
    if EXTENDED:
        attrs = b.get_asset(SYMBOL).get("attributes") or []
        step("asset_attributes", attributes=attrs)
        if "overnight_tradable" not in attrs and clock["is_open"] is False:
            fail(f"{SYMBOL} is not overnight_tradable")
        clock = {**clock, "is_open": True}          # the broker's regular-session clock does not apply to this mode
    while not clock["is_open"]:
        if NOW_ONLY:
            fail(f"market closed (next open {clock['next_open']})")
        if waited > MAX_WAIT_OPEN_S:
            fail("market did not open within the wait limit")
        time.sleep(60)
        waited += 60
        clock = b.get_clock()
    if waited:
        time.sleep(180)           # let the opening auction settle before sending a market order
    step("market_open", clock=clock, waited_s=waited)

    buy = run_order(b, "buy", "buy")
    held = position_qty(b)
    step("position_after_buy", qty=held, response=[p.__dict__ for p in b.get_positions() if p.symbol == SYMBOL])
    if abs(held - QTY) > 1e-9:
        fail(f"expected a position of {QTY}, found {held}", 5)
    try:
        sell = run_order(b, "sell", "sell")
    except SystemExit:
        print(f"!!! the {SYMBOL} position of {held} may still be OPEN on the paper account: close it by hand", file=sys.stderr)
        raise
    flat = position_qty(b)
    step("position_after_sell", qty=flat)
    activities = b._get("/v2/account/activities/FILL?page_size=20")
    mine = [a for a in activities if a.get("order_id") in (buy["id"], sell["id"])]
    step("fill_activities", matched=len(mine), activities=mine)
    pnl = (float(sell["filled_avg_price"]) - float(buy["filled_avg_price"])) * QTY
    step("reconciliation", buy_price=buy["filled_avg_price"], sell_price=sell["filled_avg_price"], pnl_usd=round(pnl, 4),
         position_flat=flat == 0, fills_match_activities=len(mine) == 2)
    print(json.dumps(log, indent=1, default=str))


main()
