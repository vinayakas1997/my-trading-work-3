"""What an Alpaca order looks like at each stage, and how to identify it.

Written from real responses captured on the paper account (see tests/fixtures/alpaca_order_lifecycle.json), not from the
documentation alone. Nothing here talks to the broker; it only describes and classifies what the broker returned.

HOW TO IDENTIFY AN ORDER
  id               broker-assigned UUID. The key for GET /v2/orders/{id} and DELETE /v2/orders/{id}.
  client_order_id  OURS (max 128 chars), sent at submit. The broker refuses a second order with the same value, so a retried
                   submit cannot double-fill; also readable via GET /v2/orders:by_client_order_id?client_order_id=...
  asset_id         the instrument's UUID; `symbol` is the readable form.
  replaced_by / replaces   link a replaced order to its successor.
  legs             child orders of a bracket / oto order (each has its own id).

STAGES (the `status` field, plus which timestamp fields fill in)
  accepted / new / pending_new     OPEN, resting at the broker (an order sent while the market is closed is `accepted`).
                                   filled_qty 0, filled_avg_price None, only created/submitted/updated timestamps set.
  partially_filled                 OPEN, filled_qty > 0 and < qty, filled_avg_price is the average so far.
  pending_cancel / pending_replace OPEN, a change was asked for and not yet confirmed.
  filled                           CLOSED: filled_at set, filled_qty == qty, filled_avg_price is the real fill price.
  canceled                         CLOSED: canceled_at set (filled_qty may still be > 0 if it partly filled first).
  expired                          CLOSED: expired_at set (a `day` order after the close, or a gtc past expires_at).
  rejected                         CLOSED: failed_at set / the submit itself returned an HTTP error with a message.
  replaced                         CLOSED: replaced_at set, replaced_by names the new order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Sent with every order. `qty` and `notional` are alternatives (exactly one).
REQUIRED_SUBMIT_FIELDS = ("symbol", "side", "type", "time_in_force", "qty")
#: Sent when the order type needs them. `client_order_id` is always sent by this project (idempotency).
OPTIONAL_SUBMIT_FIELDS = ("limit_price", "stop_price", "client_order_id", "extended_hours", "order_class", "take_profit", "stop_loss")

#: Every field a response carries (observed on a paper-account limit order, open and cancelled).
RESPONSE_FIELDS = (
    "id", "client_order_id", "created_at", "updated_at", "submitted_at", "filled_at", "expired_at", "canceled_at",
    "failed_at", "replaced_at", "replaced_by", "replaces", "asset_id", "symbol", "asset_class", "notional", "qty",
    "filled_qty", "filled_avg_price", "order_class", "order_type", "type", "side", "position_intent", "time_in_force",
    "limit_price", "stop_price", "status", "extended_hours", "legs", "trail_percent", "trail_price", "hwm", "expires_at",
    "subtag", "source",
)

#: Fields worth watching while an order is open, and what each tells you.
WATCH_WHILE_OPEN = {
    "status": "where it is in its life (see STAGES)",
    "filled_qty": "how much has filled so far",
    "filled_avg_price": "average fill price so far (None until something fills)",
    "updated_at": "last change at the broker",
    "expires_at": "when a gtc order lapses",
}
#: Fields that appear or become final once an order is closed.
READ_WHEN_CLOSED = {
    "status": "terminal state: filled | canceled | expired | rejected | replaced",
    "filled_at": "when it filled (filled only)",
    "filled_qty": "final filled quantity",
    "filled_avg_price": "the real execution price: the number to reconcile against our own record",
    "canceled_at": "when it was cancelled (canceled only)",
    "expired_at": "when it expired (expired only)",
    "failed_at": "when it failed (rejected only)",
}

OPEN_STATUSES = frozenset({
    "new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled", "pending_cancel", "pending_replace",
    "held", "calculated",
})
CLOSED_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "replaced", "done_for_day", "stopped", "suspended"})
_TERMINAL_TIMESTAMP = {
    "filled": "filled_at", "canceled": "canceled_at", "expired": "expired_at", "rejected": "failed_at",
    "replaced": "replaced_at",
}


@dataclass(frozen=True)
class OrderObservation:
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    status: str
    is_open: bool
    is_closed: bool
    qty: float
    filled_qty: float
    filled_avg_price: float | None
    closed_at: str | None
    problems: tuple[str, ...]


def _num(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def observe(raw: dict[str, Any]) -> OrderObservation:
    """Normalise one broker response and list anything inconsistent with the stage it claims (`problems`), so a caller
    reconciling an order does not trust a status without its supporting fields."""
    status = str(raw.get("status", ""))
    qty, filled = _num(raw.get("qty")) or 0.0, _num(raw.get("filled_qty")) or 0.0
    avg = _num(raw.get("filled_avg_price"))
    closed_field = _TERMINAL_TIMESTAMP.get(status)
    closed_at = raw.get(closed_field) if closed_field else None
    problems: list[str] = []
    if status not in OPEN_STATUSES | CLOSED_STATUSES:
        problems.append(f"unknown status {status!r}")
    if closed_field and not closed_at:
        problems.append(f"status {status} but {closed_field} is empty")
    if status == "filled":
        if avg is None:
            problems.append("filled but filled_avg_price is empty")
        if qty and abs(filled - qty) > 1e-9:
            problems.append(f"filled but filled_qty {filled} != qty {qty}")
    if status in ("accepted", "new", "pending_new") and filled > 0:
        problems.append(f"status {status} but filled_qty is {filled}")
    if filled > 0 and avg is None:
        problems.append("filled_qty > 0 but filled_avg_price is empty")
    if filled > qty > 0:
        problems.append(f"filled_qty {filled} exceeds qty {qty}")
    return OrderObservation(
        order_id=str(raw.get("id", "")), client_order_id=str(raw.get("client_order_id", "")), symbol=str(raw.get("symbol", "")),
        side=str(raw.get("side", "")), status=status, is_open=status in OPEN_STATUSES, is_closed=status in CLOSED_STATUSES,
        qty=qty, filled_qty=filled, filled_avg_price=avg, closed_at=closed_at, problems=tuple(problems),
    )


def missing_response_fields(raw: dict[str, Any]) -> list[str]:
    """Fields in RESPONSE_FIELDS the broker did not return (a changed API shows up here)."""
    return [f for f in RESPONSE_FIELDS if f not in raw]
