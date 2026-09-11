"""Phase 6: executes Phase 4's frozen trade plans against live data.

Reads ACTIVE `type=trade_plan` artifacts from vinu-research, enters a position when a plan is
approved and the book is flat for its symbol, evaluates contingency/invalidation rules against
live data for open positions, checks Phase 5's breaker before every single order attempt, and
reconciles Phase 3's book against the broker's actual positions at the end of every cycle. Zero
LLM calls -- every action here is a mechanical rule evaluation over a plan Phase 4 already
authored (see design decisions in the Phase 6 implementation doc). Deliberately does not import
`vinu_research.models` -- trade plans arrive as plain JSON dicts, preserving the 3-environment
isolation boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np

from vinu_live.book.positions import (
    BookBackend,
    add_to_position,
    close_position,
    daily_realized_pnl,
    init_book,
    list_open_positions,
    open_position,
    reduce_position,
    update_stop_loss,
)
from vinu_live.book.lock import book_lock, lock_path_for_book
from vinu_live.book.schema import Position
from vinu_live.breaker.engine import BreakerVerdict, check_limits
from vinu_live.breaker.limits import BreakerState
from vinu_live.config import LiveConfig, load_config
from vinu_live.reconciliation import ReconciliationEngine
from vinu_live.trade_plan.condition_evaluator import find_triggered_rules
from vinu_live.trade_plan.live_metrics import compute_live_metrics
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue
from vinu_infra.runtime_settings import RuntimeSettings

LOG = logging.getLogger(__name__)

_COVARIANCE_WINDOW = 63
_RETURNS_LOOKBACK_DAYS = 90

# Monitor safety (15 steps 1-2): HALT entries-only + time-stop + cooldown.
# entries_only = block entries, allow risk-reducing exits/reduces.
# all = block everything (old behavior, for debug rollback).
# Cooldown: N consecutive losses locks new entries for H hours (revenge block).
import os as _os
HALT_POLICY = _os.environ.get("VINU_LIVE_HALT_POLICY", "entries_only")
MAX_HOLD_DAYS = int(_os.environ.get("VINU_LIVE_MAX_HOLD_DAYS", "30"))
COOLDOWN_LOSSES = int(_os.environ.get("VINU_LIVE_COOLDOWN_LOSSES", "2"))
COOLDOWN_HOURS = float(_os.environ.get("VINU_LIVE_COOLDOWN_HOURS", "24"))


def cooldown_active(book: Any) -> tuple[bool, str]:
    """2 losses in a row -> lock entries 24h (15 step2). Exits never blocked."""
    if COOLDOWN_LOSSES <= 0 or COOLDOWN_HOURS <= 0:
        return False, ""
    try:
        import sqlite3 as _sql
        from pathlib import Path as _Path

        _dbp = getattr(book, "db_path", None)
        con = None
        if isinstance(_dbp, (str, _Path)) and _Path(str(_dbp)).exists():
            con = _sql.connect(f"file:{_dbp}?mode=ro", uri=True)
        if con is None:
            # Fallback: list_closed_positions helper shape (mocks, other backends).
            from vinu_live.book.positions import list_closed_positions as _list
            closed = _list(book)
            rows = [{"realized_pnl": c.get("realized_pnl", 0), "closed_at": c.get("closed_at", "")} for c in closed]
        else:
            try:
                cur = con.cursor()
                cur.execute("SELECT realized_pnl, closed_at FROM closed_positions ORDER BY closed_at DESC LIMIT 10")
                rows = [{"realized_pnl": r[0], "closed_at": r[1]} for r in cur.fetchall()]
            finally:
                con.close()
        streak = 0
        latest: str = ""
        for r in rows:
            if (r.get("realized_pnl") or 0) < 0:
                streak += 1
                if not latest:
                    latest = r.get("closed_at", "")
            else:
                break
        if streak < COOLDOWN_LOSSES:
            return False, ""
        if latest:
            try:
                dt = datetime.fromisoformat(latest)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - dt).total_seconds() > COOLDOWN_HOURS * 3600:
                    return False, ""
            except (ValueError, TypeError):
                pass
        return True, f"cooldown: {streak} consecutive losses, entries locked {COOLDOWN_HOURS:g}h"
    except Exception:
        return False, ""


def _halt_allows_exit() -> bool:
    return HALT_POLICY == "entries_only"


def _position_age_days(opened_at: str) -> int:
    try:
        opened = datetime.fromisoformat(opened_at)
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - opened).days
    except (ValueError, TypeError):
        return 0


TRAILING_ATR_MULT = float(_os.environ.get("VINU_LIVE_TRAILING_ATR_MULT", "2.0"))
# Stage A (A7 -- Hummingbot's TrailingStop.activation_price, see
# other-repos-world/comprison-other-vinu/06-hummingbot.md): the trailing
# stop stays inert until the position is up by this fraction. Before that
# a normal post-entry pullback would ratchet a stop in and take the trade
# out before it had a chance to work; the plan's fixed invalidation/
# contingency stops still cover the position in the meantime. 0.0 (default)
# keeps the pre-A7 behaviour of trailing from entry.
TRAILING_ACTIVATION_PCT = float(_os.environ.get("VINU_LIVE_TRAILING_ACTIVATION_PCT", "0.0"))
TURBULENCE_VOL = float(_os.environ.get("VINU_LIVE_TURBULENCE_VOL", "0.05"))

# Stage 2 (how-to-make-it-live.md #24): TradePlan.forecast.confidence was
# computed by research/the LLM but never read at the one place a TradePlan's
# size is actually decided (this file's _maybe_enter). Same
# forecast_confidence_scale formula as vinu-agent/agent/position_sizing.py
# -- duplicated rather than imported because vinu-live and vinu-agent are
# separate deployable services with no shared package for this, same reason
# this file already reimplements small pieces of shared logic locally
# elsewhere (see daily-allocation's own note on regime_analysis). Defaults
# ON, same reasoning as position_sizing.py's copy: this closes a silent
# "the data exists but nothing reads it" gap, it isn't a new optional extra.
FORECAST_SCALING_ENABLED = _os.environ.get(
    "VINU_RISK_FORECAST_SCALING_ENABLED", "true"
).lower() in ("1", "true", "yes")
FORECAST_SCALING_FLOOR = float(_os.environ.get("VINU_RISK_FORECAST_SCALING_FLOOR", "0.5"))


SIGNAL_MAX_AGE_HOURS = float(_os.environ.get("VINU_LIVE_SIGNAL_MAX_AGE_HOURS", "72"))


# how-to-make-it-live.md #17: the CVaR tail gate + dynamic vol targeting were
# built in vinu-agent/agent/position_sizing.py (cvar_exceeds / vol_target_scale)
# and gated behind VINU_RISK_CVAR_ENABLED / VINU_RISK_VOL_TARGET_ENABLED -- but
# no caller on the live path ever fed them cvar_95 / current_vol, so flipping
# the flags did nothing. _maybe_enter() is the one place a live TradePlan's
# size is actually decided; it now reads the CVaR + daily vol frozen onto
# RiskBand at authoring time (trade_plan_authoring._build_risk_band) and
# applies the same two controls here, same env var names as the vinu-agent
# copy so there is one knob per control, not two that can disagree.
# CVaR gate defaults OFF (a hard block -- opt in deliberately); vol targeting
# too, matching the historical default the flags shipped with.
CVAR_GATE_ENABLED = _os.environ.get(
    "VINU_RISK_CVAR_ENABLED", "false"
).lower() in ("1", "true", "yes")
CVAR_THRESHOLD = float(_os.environ.get("VINU_RISK_CVAR_THRESHOLD", "0.03"))
VOL_TARGET_ENABLED = _os.environ.get(
    "VINU_RISK_VOL_TARGET_ENABLED", "false"
).lower() in ("1", "true", "yes")
VOL_TARGET = float(_os.environ.get("VINU_RISK_VOL_TARGET", "0.15"))


def _vol_target_scale(current_vol: Any, target_vol: float = VOL_TARGET) -> float:
    """target_vol / current_vol, so size halves when realized vol doubles.
    current_vol here is the plan's frozen *daily* vol; target_vol is annual
    (0.15), so it is converted to a daily figure (/ sqrt(252)) before the
    ratio -- same units on both sides. Non-positive / unparseable current_vol
    = 1.0 (no scaling, fail-open). Never scales size *up* past 1.0 -- a calm
    market does not license extra leverage here."""
    try:
        cur = float(current_vol)
    except (TypeError, ValueError):
        return 1.0
    if cur <= 0.0 or target_vol <= 0.0:
        return 1.0
    target_daily = target_vol / (252.0 ** 0.5)
    return min(1.0, target_daily / cur)


# how-to-make-it-live.md #16 (Stage 3): data-freshness guard. The live cycle
# fetches interval=1d candles; if the ingest pipeline stalls (provider outage,
# dead ingest worker) the newest bar just stops advancing and every entry
# decision is made on a stale mark with nothing noticing. This pauses ENTRIES
# only (exits/reduces must always proceed -- same shape as HALT entries-only,
# turbulence, and cooldown). Threshold is wall-clock hours since the newest
# bar's open (bar_ts, UTC epoch seconds). 96h default tolerates a 3-day
# weekend + buffer on daily bars while still catching a feed that is genuinely
# days behind; TIGHTEN THIS if you run intraday intervals. 0 disables.
PRICE_MAX_AGE_HOURS = float(_os.environ.get("VINU_LIVE_PRICE_MAX_AGE_HOURS", "96"))


def _price_ts_age_hours(bar_ts: Any) -> float | None:
    """Hours since `bar_ts` (UTC epoch seconds). None (never blocks) if bar_ts
    is missing / non-numeric / non-positive -- fail-open, same posture as every
    other data-quality guard in this file."""
    try:
        ts = float(bar_ts)
    except (TypeError, ValueError):
        return None
    if ts <= 0.0:
        return None
    return (datetime.now(timezone.utc).timestamp() - ts) / 3600.0


# how-to-make-it-live.md #15 (Stage 3): partial-fill handling. The order path
# books the INTENDED qty the moment /agent/broker/order returns "submitted" --
# but a market order can partially fill (thin book), and the fill lands async,
# so the response carries no filled_qty. Every later risk check / exit sizing /
# P&L calc then runs off a size the account never actually held. Two backstops:
#   (1) right after a submit, poll the broker's real position a few times and
#       book what actually filled (fail open to intended if the broker view is
#       unavailable -- reconciliation below is the net);
#   (2) end-of-cycle reconciliation stops only warning and actually pulls the
#       book back to broker truth when they disagree.
FILL_CONFIRM_ATTEMPTS = int(_os.environ.get("VINU_LIVE_FILL_CONFIRM_ATTEMPTS", "3"))
FILL_CONFIRM_DELAY_SEC = float(_os.environ.get("VINU_LIVE_FILL_CONFIRM_DELAY_SEC", "0.7"))
# A fill within this fraction of intended counts as "full" -- covers share
# rounding / tiny broker-vs-book quantization noise, not a real partial.
PARTIAL_FILL_TOLERANCE = float(_os.environ.get("VINU_LIVE_PARTIAL_FILL_TOLERANCE", "0.02"))
# End-of-cycle reconciliation: pull the book toward broker truth on drift
# instead of only logging. 0/false = warn-only (the old behavior).
RECONCILE_AUTOCORRECT = _os.environ.get(
    "VINU_LIVE_RECONCILE_AUTOCORRECT", "true"
).lower() in ("1", "true", "yes")
# A book/broker gap this many times the book size is a bug, not a partial fill
# -- reconciliation refuses to auto-correct past it and alerts instead.
RECONCILE_MAX_RATIO = float(_os.environ.get("VINU_LIVE_RECONCILE_MAX_RATIO", "10.0"))
# A symbol this instance placed an order on within this many seconds is skipped
# by auto-correct: the broker's /positions endpoint lags a fresh fill by up to
# ~1s, and reconciling against that stale view trims a correct book position.
# The next cycle (order settled) reconciles it normally. 0 disables the defer.
RECONCILE_SETTLE_SEC = float(_os.environ.get("VINU_LIVE_RECONCILE_SETTLE_SEC", "12"))


# how-to-make-it-live.md #12 (Stage 3): runtime correlation monitor. The
# DCC/shrinkage covariance (_compute_covariance) was only ever consulted by the
# breaker's aggregate-VaR check -- nothing looked at pairwise correlation
# between the positions actually open and de-risked when two of them started
# moving together. This runs every cycle: covariance -> correlation, flag any
# pair whose co-movement *in the direction we're exposed* is >= threshold, and
# reduce_only-shrink the larger position of the pair. reduce_only means it can
# only ever cut risk, never add it. Per-symbol cooldown so it trims once, not
# every 90s. Defaults ON -- Scenario 12 is a rated portfolio-blowup gap and the
# action is bounded and risk-reducing.
RUNTIME_CORR_ENABLED = _os.environ.get(
    "VINU_LIVE_RUNTIME_CORR_ENABLED", "true"
).lower() in ("1", "true", "yes")
RUNTIME_CORR_THRESHOLD = float(_os.environ.get("VINU_LIVE_RUNTIME_CORR_THRESHOLD", "0.85"))
RUNTIME_CORR_REDUCE_PCT = float(_os.environ.get("VINU_LIVE_RUNTIME_CORR_REDUCE_PCT", "0.25"))
RUNTIME_CORR_COOLDOWN_SEC = float(_os.environ.get("VINU_LIVE_RUNTIME_CORR_COOLDOWN_SEC", "3600"))

# Live-editable overrides for the three tunables above, via
# POST /live/admin/settings -- no restart needed. RUNTIME_CORR_ENABLED
# stays a boot-only flag (feature kill switches belong in `.env`, not a
# runtime HTTP surface); only the numeric thresholds are registered.
# `SETTINGS.get(...)` always wins over the module constant when read
# through the helpers below, so existing callers that still reference
# RUNTIME_CORR_THRESHOLD/REDUCE_PCT/COOLDOWN_SEC directly (e.g. log lines)
# see the `.env` default, not a live override -- only _check_runtime_correlation
# itself reads the live value, via runtime_corr_threshold()/_reduce_pct()/_cooldown_sec().
SETTINGS = RuntimeSettings()
SETTINGS.register(
    "runtime_corr_threshold",
    default=RUNTIME_CORR_THRESHOLD,
    minimum=0.0,
    maximum=1.0,
    description="Co-movement threshold above which the runtime correlation monitor trims a pair.",
)
SETTINGS.register(
    "runtime_corr_reduce_pct",
    default=RUNTIME_CORR_REDUCE_PCT,
    minimum=0.0,
    maximum=1.0,
    description="Fraction of the larger position's qty to reduce when the pair trips the threshold.",
)
SETTINGS.register(
    "runtime_corr_cooldown_sec",
    default=RUNTIME_CORR_COOLDOWN_SEC,
    minimum=0.0,
    description="Per-symbol seconds between runtime-correlation reductions.",
)


def runtime_corr_threshold() -> float:
    return SETTINGS.get("runtime_corr_threshold")


def runtime_corr_reduce_pct() -> float:
    return SETTINGS.get("runtime_corr_reduce_pct")


def runtime_corr_cooldown_sec() -> float:
    return SETTINGS.get("runtime_corr_cooldown_sec")


# how-to-make-it-live.md #3/#5 (Stage 3): conflicting-signal detection. More
# than one ACTIVE trade_plan can name the same symbol (a 1D sweep and a 1H
# sweep, say). Nothing checked whether they agreed -- whichever plan the cycle
# happened to evaluate first opened a position and the opposing plan was
# silently ignored, so the book could hold a long that another live, promoted
# strategy currently says to be short. "block" (default) refuses to open into a
# contested symbol; "ignore" restores the old first-plan-wins behavior.
SIGNAL_CONFLICT_POLICY = _os.environ.get("VINU_LIVE_SIGNAL_CONFLICT_POLICY", "block").lower()


def _opposing_active_signal(
    plan: dict[str, Any], symbol: str, direction: str, all_plans: list[dict[str, Any]],
) -> str | None:
    """how-to-make-it-live.md #3/#5: a reason string if another ACTIVE plan for
    `symbol` currently signals the opposite direction, else None."""
    opposite = "short" if direction == "long" else "long"
    my_id = plan.get("_artifact_id")
    conflicting = [
        p.get("_artifact_id", "?")
        for p in all_plans
        if p.get("symbol") == symbol
        and p.get("_artifact_id") != my_id
        and p.get("direction") == opposite
    ]
    if not conflicting:
        return None
    return f"{len(conflicting)} other ACTIVE plan(s) signal {opposite}: {', '.join(map(str, conflicting))}"


# how-to-make-it-live.md #13 (Stage 4): liquidity / spread gate. Every entry so
# far was priced off the last 1d candle close, with no check on whether the
# symbol is actually tradable *right now* at a sane cost. A wide bid/ask (thin
# pre-market, a halt-then-reopen, a small-cap air pocket) means the market order
# crosses that spread and fills materially worse than the mark the sizing used.
# This fetches the live NBBO from vinu-stock-price (5s-cached there -> one
# upstream call per burst) only when an entry is otherwise a go, and blocks the
# entry when the spread in basis points exceeds the ceiling. ENTRIES ONLY -- an
# exit/reduce still crosses whatever spread it must (same shape as HALT
# entries-only / turbulence / cooldown / data-freshness). Fail-open: no quote /
# quote error / service down => entry proceeds. 0 disables. 25 bps = 0.25%.
MAX_SPREAD_BPS = float(_os.environ.get("VINU_LIVE_MAX_SPREAD_BPS", "25"))


def _spread_bps_from_quote(payload: Any) -> float | None:
    """Basis-point spread from a vinu-stock-price /stock/quote payload, or None
    (never blocks) when the payload is missing / not `ok` / unparseable /
    negative -- fail-open, same posture as every other data-quality guard in
    this file."""
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    try:
        sb = float(payload.get("spread_bps"))
    except (TypeError, ValueError):
        return None
    if sb < 0.0:
        return None
    return sb


# how-to-make-it-live.md #14 (Stage 4): broker-outage pause. Half A -- no new
# data source, uses the existing /agent/broker/account probe. Once per cycle
# _check_broker_health() pings the broker; a healthy 200 stamps a monotonic
# clock and clears the flag, a non-200 / transport error that persists past
# BROKER_STALE_SEC sets self._broker_degraded. _maybe_enter refuses new entries
# while degraded (entry_blocked_by_broker_outage); exits/reduces are never
# gated (same entries-only shape as HALT / turbulence / cooldown / spread). The
# flag auto-clears on the next healthy probe. 0 disables the guard entirely.
# 180s tolerates a transient blip spanning two 90s cycles without pausing.
BROKER_STALE_SEC = float(_os.environ.get("VINU_LIVE_BROKER_STALE_SEC", "180"))


# how-to-make-it-live.md #2 (Stage 4): event-risk blackout. vinu-stock-price
# keeps a local earnings + US-macro (FOMC/CPI/NFP/PCE) calendar, refreshed daily
# from Finnhub. If the symbol has an event inside this many hours, do not open a
# new position -- an earnings gap or an FOMC whipsaw is exactly the kind of jump
# a mean-reversion / trend setup was never edged for. ENTRIES ONLY (an open
# position's own invalidation/contingency rules still run through an event).
# Fail-open: calendar service down, no Finnhub key, or no rows => entry
# proceeds. 0 disables. 24h covers "don't open the day before earnings".
EVENT_BLACKOUT_HOURS = float(_os.environ.get("VINU_LIVE_EVENT_BLACKOUT_HOURS", "24"))


# how-to-make-it-live.md #33 part 2 (Stage 4): out-of-distribution detector --
# the AUTOMATIC trigger for the emergency flatten. Ships DORMANT. Once per cycle
# it scores three fail-open signals over the open book and fires only when
# >= OOD_MIN_SIGNALS of them trip together (so no single noisy input can nuke
# the book). Graduated activation via VINU_LIVE_OOD_DETECTOR:
#   off     (default) -- not even run
#   alert             -- detect + log + report in the cycle result, NO action
#                        (run this for weeks in paper and see how often it fires)
#   halt              -- trip the global kill switch (block new entries)
#   flatten           -- full emergency_flatten()
# Latched: after it acts once (this process lifetime) it will not act again
# until emergency_resume() or a restart -- an auto-flatten is a one-shot, not a
# loop.
OOD_DETECTOR_MODE = _os.environ.get("VINU_LIVE_OOD_DETECTOR", "off").lower()
OOD_CORR_THRESHOLD = float(_os.environ.get("VINU_LIVE_OOD_CORR", "0.95"))
OOD_VOL_THRESHOLD = float(_os.environ.get("VINU_LIVE_OOD_VOL", "0.08"))
OOD_MOVE_THRESHOLD = float(_os.environ.get("VINU_LIVE_OOD_MOVE", "0.10"))
OOD_MIN_SIGNALS = int(_os.environ.get("VINU_LIVE_OOD_MIN_SIGNALS", "2"))
# Stage A (A10 -- FinRL's turbulence index, see other-repos-world/
# comprison-other-vinu/08-finrl.md): a 4th OOD signal. Mahalanobis distance
# of today's joint return vector from its recent distribution -- catches a
# statistically extreme *joint configuration* of returns even when no
# single symbol's vol and no single pairwise correlation looks abnormal on
# its own. Under multivariate normality E[MD^2] = n (dimension count), so
# the threshold is a multiple of the open-book size; default 5x only fires
# on a genuinely extreme joint move.
OOD_TURBULENCE_MULT = float(_os.environ.get("VINU_LIVE_OOD_TURBULENCE_MULT", "5.0"))


def _signal_age_hours(created_at: Any) -> float | None:
    """Stage 2 (how-to-make-it-live.md #9/#36): a TradePlan was "valid until
    invalidated," never "valid for a window" -- a 3-day-old setup with no
    fill was still actionable, because nothing ever read the timestamp
    trade_plan_authoring.py's author_trade_plan() already stamps on every
    plan (TradePlan.created_at, set at generation time and carried through
    Artifact.trade_plan_data -- this file already reads that same dict for
    every other field). Returns None (unknown age, never blocks) if
    created_at is missing or unparseable -- fail-open, same posture as
    every other data-quality guard in this file."""
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(str(created_at))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return None


def _forecast_confidence_scale(confidence: Any, floor: float = FORECAST_SCALING_FLOOR) -> float:
    """confidence as a direct fraction of the plan's own max size, floored
    so a real forecast is dampened, never zeroed, by conviction alone.
    None/non-positive confidence = 1.0 (no scaling, fail-open)."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return 1.0
    if c <= 0.0:
        return 1.0
    return max(float(floor), min(1.0, c))


async def turbulence_active(fetch_recent: Any, symbol: str) -> tuple[bool, str]:
    """Turbulence VIX pause (15 step3): 14d realized vol above threshold ->
    pause entries (exits never blocked). Fail-open on missing data."""
    if TURBULENCE_VOL <= 0:
        return False, ""
    try:
        prices = await fetch_recent(symbol)
        if len(prices) < 15:
            return False, ""
        import statistics as _st

        rets = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices)) if prices[i - 1] > 0]
        vol = _st.pstdev(rets[-14:]) if len(rets) >= 14 else 0.0
        if vol > TURBULENCE_VOL:
            return True, f"turbulence: 14d vol {vol:.3f} > {TURBULENCE_VOL:.3f}, entries paused"
        return False, ""
    except Exception:
        return False, ""


def trailing_stop_for(position: Any, price: float, closes: list[float]) -> float | None:
    """Trailing 2x ATR stop (15 step2): mean absolute daily move over last 14
    closes as ATR proxy. Long: price - mult*ATR. Short: price + mult*ATR.
    Returns None when not enough data, or (Stage A / A7) when the position
    has not yet gained TRAILING_ACTIVATION_PCT. Ratchet-only enforced by
    caller."""
    if TRAILING_ATR_MULT <= 0 or len(closes) < 3 or price <= 0:
        return None
    if TRAILING_ACTIVATION_PCT > 0:
        entry = float(getattr(position, "avg_entry", 0.0) or 0.0)
        _side = str(getattr(position, "side", getattr(position, "direction", "long"))).lower()
        if entry > 0:
            gain_pct = (
                (entry - price) / entry if _side in ("short", "sell")
                else (price - entry) / entry
            )
            if gain_pct < TRAILING_ACTIVATION_PCT:
                return None
    window = closes[-15:]
    moves = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
    atr = sum(moves) / len(moves) if moves else 0.0
    if atr <= 0:
        return None
    side = getattr(position, "side", getattr(position, "direction", "long"))
    if str(side).lower() in ("short", "sell"):
        return price + TRAILING_ATR_MULT * atr
    return price - TRAILING_ATR_MULT * atr


class TradePlanOrchestrator:
    def __init__(
        self,
        config: LiveConfig | None = None,
        book: BookBackend | None = None,
        rebalance_queue: RebalanceRequestQueue | None = None,
    ) -> None:
        self._config = config or load_config()
        try:
            from vinu_infra.auth import internal_auth_headers
            _headers = internal_auth_headers() or None
        except Exception:
            _headers = None
        self._http = httpx.AsyncClient(timeout=30.0, headers=_headers)
        self._book = book or init_book(str(self._config.data_root / "trade_plan_book.db"))
        # how-to-make-it-live.md #35 fix: cross-process lock guarding every
        # "read book -> decide -> write book" section, so the long-running
        # worker and a throwaway HTTP-route orchestrator cannot double-apply a
        # correction. Path is derived from the actual book db file (a temp file
        # in tests, ":memory:" -> disabled).
        self._book_lock_path = lock_path_for_book(getattr(self._book, "_db_path", None))
        # Per-symbol monotonic time of the last order this instance placed, so
        # end-of-cycle reconciliation can DEFER a symbol whose fill has not had
        # time to propagate to the broker's position endpoint yet (observed:
        # reconcile trimmed a correct 5.74-share book to ~1 because Alpaca's
        # /positions lagged the fill by <1s).
        self._recently_traded: dict[str, float] = {}
        self._breaker_state = BreakerState()
        self._reconciler = ReconciliationEngine()
        self._cycle_count = 0
        self._last_prices: dict[str, float] = {}
        # how-to-make-it-live.md #16: newest bar_ts (UTC epoch seconds) per
        # symbol from the last _fetch_prices, so _maybe_enter can pause entries
        # on a stale feed. Populated alongside _last_prices.
        self._last_price_ts: dict[str, float] = {}
        # Phase 5: advisory intake for capital_allocator's rebalance
        # requests -- never a direct action, folded into the ordinary
        # per-cycle evaluation below, after the plan's own real
        # invalidation/contingency rules, never before them. SQLite-backed
        # at a shared, on-disk path (not per-instance in-memory) so a
        # request submitted via the HTTP intake route's own throwaway
        # TradePlanOrchestrator instance (server/app.py constructs a fresh
        # one per request) is still visible to the long-running
        # trade-plan-worker's orchestrator on its next real cycle.
        # Injectable (same DI pattern as `book` above) so tests get an
        # isolated queue instead of sharing config.data_root's real file.
        self._rebalance_queue = rebalance_queue or RebalanceRequestQueue(
            str(self._config.data_root / "rebalance_requests.db"),
        )
        # Phase 5: per-symbol debounce for the shock-angle trigger below --
        # monotonic clock, not wall time (immune to clock adjustments).
        self._last_shock_trigger: dict[str, float] = {}
        # how-to-make-it-live.md #12: per-symbol monotonic time of the last
        # correlation-triggered reduce, so the monitor trims a name once and
        # then leaves it alone for RUNTIME_CORR_COOLDOWN_SEC.
        self._last_corr_reduce: dict[str, float] = {}
        # how-to-make-it-live.md #14 (Stage 4): broker-outage pause. Monotonic
        # time of the last successful /agent/broker/account probe (0.0 = never
        # confirmed yet, so a cold start with a dead broker pauses on the first
        # failed probe rather than after the grace window), and the derived
        # flag _maybe_enter reads to pause ENTRIES while the broker link is
        # down/stale. Exits and reduces are never gated on it.
        self._broker_ok_at: float = 0.0
        self._broker_degraded: bool = False
        # how-to-make-it-live.md #33 (Stage 4): mirror of the agent's global
        # kill switch, refreshed once per cycle. True => _maybe_enter refuses
        # new entries with entry_blocked_by_emergency_halt. The authoritative
        # gate is still OrderGuard's filesystem kill-switch check on the agent
        # side; this is the fast, explicit local shortcut. Set by
        # emergency_flatten(), cleared by emergency_resume().
        self._trading_halted: bool = False
        # how-to-make-it-live.md #33 part 2: latch so the auto-OOD detector
        # acts at most once per process lifetime (until emergency_resume /
        # restart).
        self._ood_acted: bool = False

    async def close(self) -> None:
        await self._http.aclose()
        self._book.close()
        self._rebalance_queue.close()

    def submit_rebalance_request(self, symbol: str, reason: str, critical: bool = False) -> None:
        """Called by whatever eventually implements capital_allocator's
        rebalancer (vinu-agent, a separate container) via this
        orchestrator's HTTP intake route -- see server/app.py. Accepting
        the request here only means it will be CONSIDERED on this
        symbol's next evaluation, not that it will be honored.

        how-to-make-it-live.md #23: `critical=True` makes the request bypass
        the 5% unrealized-gain protect in _evaluate_rebalance_request -- for a
        genuinely urgent reallocation that must not sit declined."""
        self._rebalance_queue.submit(symbol, reason, critical=critical)

    # Provisional, not tuned -- same "flag it, don't pretend it's settled"
    # discipline as _REBALANCE_PROTECT_GAIN_PCT above. Long enough that a
    # genuine burst of shock events (the exact scenario this trigger
    # exists to react to quickly) produces exactly one off-cycle check,
    # not one per event.
    _SHOCK_DEBOUNCE_SEC = 60.0

    async def on_shock_event(self, symbol: str) -> dict[str, Any] | None:
        """Off-cycle trigger (Phase 5, 01-plan.md item 3): shock_
        clustering/shock_personality fired for `symbol`. Runs the exact
        same per-symbol evaluation cycle() uses for its own per-plan loop,
        just off-schedule for this one symbol -- not a separate decision
        path. Debounced per symbol so a genuine burst of shock events
        produces exactly one check, not a cost-runaway (02-guard-rail.md).
        Returns None when debounced, no matching active plan, or no live
        price -- all silent no-ops by design (an off-cycle miss is
        recovered by the next scheduled cycle() regardless)."""
        symbol = symbol.upper()
        now = time.monotonic()
        last = self._last_shock_trigger.get(symbol)
        if last is not None and (now - last) < self._SHOCK_DEBOUNCE_SEC:
            return None
        self._last_shock_trigger[symbol] = now

        plans = await self._fetch_active_trade_plans()
        plan = next((p for p in plans if p.get("symbol") == symbol), None)
        if plan is None:
            return None

        prices = await self._fetch_prices([symbol])
        price = prices.get(symbol)
        if price is None:
            return None
        portfolio_value = await self._fetch_portfolio_value()

        position = self._find_open_position(symbol)
        if position is None:
            return await self._maybe_enter(plan, symbol, price, portfolio_value, all_plans=plans)
        return await self._evaluate_open_position(plan, position, price, portfolio_value)

    async def cycle_shock_batch(self, max_batch: int = 5) -> dict[str, Any]:
        """Batch/prioritized shock evaluation (pending Row 3 / 04:383).

        Iterates all open positions, fetches shock clustering score for
        each, sorts descending by shock correlation (highest risk first),
        and runs `on_shock_event` for the top `max_batch` symbols.
        Respects per-symbol debounce inside `on_shock_event`, so burst
        calls remain idempotent. Returns summary with prioritized order.
        """
        positions = list_open_positions(self._book)
        if not positions:
            return {"status": "skipped_no_open_positions", "actions": []}

        # Score each open symbol by shock correlation (higher = higher priority)
        scored: list[tuple[str, float]] = []
        for pos in positions:
            corr = await self._fetch_shock_cluster_correlation(pos.symbol)
            score = float(corr) if corr is not None else 0.0
            # Also incorporate shock_personality if available
            pers = await self._fetch_shock_personality_score(pos.symbol)
            if pers is not None:
                score = max(score, float(pers))
            scored.append((pos.symbol, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        batch_symbols = [s for s, _ in scored[:max_batch]]

        actions: list[dict[str, Any]] = []
        for sym in batch_symbols:
            res = await self.on_shock_event(sym)
            if res is not None:
                actions.append(res)

        return {
            "status": "ok",
            "prioritized": [s for s, _ in scored],
            "batch_symbols": batch_symbols,
            "actions": actions,
        }

    async def _fetch_shock_personality_score(self, symbol: str) -> float | None:
        """Fetch shock_personality angle score for symbol (if available)."""
        try:
            resp = await self._http.get(
                f"{self._config.initial_analysis_api_url}/analysis/angle/shock_personality/{symbol}",
            )
            if resp.status_code != 200:
                return None
            rows = resp.json().get("data", [])
            if not rows:
                return None
            last = rows[-1] or {}
            # Personality angle may expose shock_score or correlation field
            for key in ("shock_score", "personality_score", "shock_correlation", "score"):
                if key in last and last[key] is not None:
                    return float(last[key])
            return None
        except Exception as e:
            LOG.debug("Could not fetch shock personality for %s: %s", symbol, e)
            return None

    async def cycle(self) -> dict[str, Any]:
        self._cycle_count += 1
        cycle_id = f"tp_cycle_{self._cycle_count}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        LOG.info("[%s] Starting trade-plan cycle", cycle_id)

        result: dict[str, Any] = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "actions": [],
        }

        try:
            plans = await self._fetch_active_trade_plans()
            if not plans:
                result["status"] = "skipped_no_active_plans"
                return result

            symbols = sorted({p["symbol"] for p in plans if p.get("symbol")})
            prices = await self._fetch_prices(symbols)
            portfolio_value = await self._fetch_portfolio_value()

            # how-to-make-it-live.md #14: one broker liveness probe, BEFORE the
            # plan loop, so _maybe_enter this cycle sees fresh broker state
            # (degraded => entries paused). Exits in the loop are unaffected.
            result["broker_health"] = await self._check_broker_health()

            # how-to-make-it-live.md #33: refresh the global kill-switch mirror
            # before the plan loop too, so an emergency flatten from another
            # process is honoured on the very next cycle.
            self._trading_halted = await self._is_trading_halted()
            result["trading_halted"] = self._trading_halted

            # G: auto-wire prioritized shock batch — sort plans by shock score descending
            # so highest-risk open position evaluated first in same cycle (not just via
            # explicit cycle_shock_batch caller). Threshold 0.5 filters low scores.
            try:
                shock_scores: dict[str, float] = {}
                for sym in symbols:
                    corr = await self._fetch_shock_cluster_correlation(sym)
                    pers = await self._fetch_shock_personality_score(sym)
                    score = 0.0
                    if corr is not None:
                        score = max(score, float(corr))
                    if pers is not None:
                        score = max(score, float(pers))
                    shock_scores[sym] = score
                # Only re-sort if any score >0.5 (genuine shock), else keep sorted() order
                if any(s > 0.5 for s in shock_scores.values()):
                    plans = sorted(plans, key=lambda p: shock_scores.get(p.get("symbol", ""), 0.0), reverse=True)
                    LOG.info("Shock batch prioritized order: %s", [f"{p.get('symbol')}={shock_scores.get(p.get('symbol'),0):.2f}" for p in plans])
            except Exception as e:
                LOG.debug("Shock prioritization failed, using sorted order: %s", e)

            actions: list[dict[str, Any]] = []
            for plan in plans:
                symbol = plan.get("symbol", "")
                price = prices.get(symbol)
                if not symbol or price is None:
                    LOG.warning("No live price for %s -- skipping this cycle", symbol)
                    continue

                position = self._find_open_position(symbol)
                if position is None:
                    action = await self._maybe_enter(plan, symbol, price, portfolio_value, all_plans=plans)
                else:
                    action = await self._evaluate_open_position(plan, position, price, portfolio_value)
                if action:
                    actions.append(action)

            result["actions"] = actions
            self._last_prices = prices

            recon = await self._reconcile_book_with_broker(prices)
            result["reconciliation"] = recon

            corr_check = await self._check_runtime_correlation(prices)
            result["correlation_monitor"] = corr_check

            # how-to-make-it-live.md #33 part 2: auto-OOD detector. Dormant
            # unless VINU_LIVE_OOD_DETECTOR is alert/halt/flatten. Runs last
            # so it sees the book after the correlation monitor's trims.
            result["ood_detector"] = await self._check_ood(prices)

        except Exception as e:
            LOG.error("[%s] Cycle failed: %s", cycle_id, e)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    # ------------------------------------------------------------------
    # Trade-plan fetching
    # ------------------------------------------------------------------

    async def _fetch_active_trade_plans(self) -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/artifacts",
                params={"status": "ACTIVE", "type_": "trade_plan"},
            )
            if resp.status_code != 200:
                return []
            summaries = resp.json()
        except Exception as e:
            LOG.warning("Failed to list active trade plans: %s", e)
            return []

        plans: list[dict[str, Any]] = []
        for summary in summaries:
            artifact_id = summary.get("artifact_id")
            if not artifact_id:
                continue
            try:
                detail_resp = await self._http.get(
                    f"{self._config.research_api_url}/research/trade-plan/{artifact_id}",
                )
                if detail_resp.status_code != 200:
                    continue
                raw = detail_resp.json().get("trade_plan_data")
                if not raw:
                    continue
                plan = json.loads(raw)
                plan["_artifact_id"] = artifact_id
                plans.append(plan)
            except Exception as e:
                LOG.warning("Failed to fetch trade plan %s: %s", artifact_id, e)
        return plans

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    async def _maybe_enter(
        self, plan: dict[str, Any], symbol: str, price: float, portfolio_value: float,
        all_plans: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        direction = plan.get("direction", "neutral")
        if direction not in ("long", "short"):
            return None

        # how-to-make-it-live.md #33: emergency halt. The agent's global kill
        # switch is set (emergency_flatten, or a manual /agent/broker/halt).
        # OrderGuard already rejects every order while it's set; this makes the
        # block explicit and skips the wasted round-trip. Exits are unaffected
        # -- _apply_invalidation / _apply_contingency submit reduce_only orders,
        # which the kill switch's reduce_only exemption lets through.
        if self._trading_halted:
            LOG.warning("Trading halt active -- skipping entry for %s", symbol)
            return {
                "symbol": symbol, "action": "entry_blocked_by_emergency_halt",
                "reason": "global trading halt active (emergency flatten / manual halt)",
            }

        # how-to-make-it-live.md #14: broker-outage pause. If this cycle's
        # health probe (_check_broker_health, run before the plan loop) found
        # the broker link down or stale, do not open new positions -- an entry
        # we cannot confirm is worse than a missed one. Exits/reduces are
        # unaffected (_evaluate_open_position never checks this). Auto-clears
        # when the broker responds again.
        if BROKER_STALE_SEC > 0 and self._broker_degraded:
            LOG.warning("Broker degraded -- skipping entry for %s", symbol)
            return {
                "symbol": symbol, "action": "entry_blocked_by_broker_outage",
                "reason": "broker health probe failing -- entries paused until it recovers",
            }

        # how-to-make-it-live.md #3/#5: refuse to open into a symbol another
        # ACTIVE plan currently signals the opposite way on.
        if all_plans and SIGNAL_CONFLICT_POLICY == "block":
            conflict = _opposing_active_signal(plan, symbol, direction, all_plans)
            if conflict:
                LOG.warning("Signal conflict on %s -- %s -- skipping entry", symbol, conflict)
                return {
                    "symbol": symbol, "action": "entry_blocked_by_signal_conflict",
                    "reason": conflict,
                }

        if SIGNAL_MAX_AGE_HOURS > 0:
            age_hours = _signal_age_hours(plan.get("created_at"))
            if age_hours is not None and age_hours > SIGNAL_MAX_AGE_HOURS:
                LOG.info(
                    "Trade plan for %s is %.1fh old (max %.1fh) -- skipping stale entry",
                    symbol, age_hours, SIGNAL_MAX_AGE_HOURS,
                )
                return {
                    "symbol": symbol, "action": "entry_blocked_by_stale_signal",
                    "reason": f"signal age {age_hours:.1f}h exceeds max {SIGNAL_MAX_AGE_HOURS:.1f}h",
                }

        # how-to-make-it-live.md #16: data-freshness guard. Pause ENTRIES when
        # the newest price bar for this symbol is older than the threshold --
        # trading on a mark from a stalled feed. Exits are never gated here
        # (see _evaluate_open_position: it only logs). Fail-open when we have
        # no timestamp for the symbol (first cycle, mock, ts-less feed).
        if PRICE_MAX_AGE_HOURS > 0:
            data_age = _price_ts_age_hours(self._last_price_ts.get(symbol))
            if data_age is not None and data_age > PRICE_MAX_AGE_HOURS:
                LOG.warning(
                    "Price feed for %s is %.1fh stale (max %.1fh) -- pausing entry",
                    symbol, data_age, PRICE_MAX_AGE_HOURS,
                )
                return {
                    "symbol": symbol, "action": "entry_blocked_by_stale_data",
                    "reason": f"price data age {data_age:.1f}h exceeds max {PRICE_MAX_AGE_HOURS:.1f}h",
                }

        risk_bands = plan.get("risk_bands") or {}
        size_pct = risk_bands.get("max_position_size_pct", 0.0) or 0.0
        if size_pct <= 0:
            LOG.info("Trade plan for %s has no position size -- skipping entry", symbol)
            return None

        # how-to-make-it-live.md #17: CVaR tail gate. cvar_95_limit is frozen
        # onto the plan at authoring time; 0.0 means it was never computed, so
        # the gate is skipped (fail-open, same posture as every other
        # data-quality guard here). A real value above threshold blocks the
        # entry outright -- this is a "the tail on this name is too fat to
        # open here" call, not a sizing tweak.
        if CVAR_GATE_ENABLED:
            cvar_95 = risk_bands.get("cvar_95_limit", 0.0) or 0.0
            if cvar_95 > CVAR_THRESHOLD:
                LOG.warning(
                    "Trade plan for %s: CVaR 95%% %.3f exceeds %.3f -- blocking entry",
                    symbol, cvar_95, CVAR_THRESHOLD,
                )
                return {
                    "symbol": symbol, "action": "entry_blocked_by_cvar",
                    "reason": f"CVaR 95% {cvar_95:.3f} exceeds max {CVAR_THRESHOLD:.3f}",
                }

        # how-to-make-it-live.md #2: event-risk blackout. Ask vinu-stock-price's
        # local calendar whether this symbol has an earnings / macro event
        # inside the window; if so, do not open. ENTRIES ONLY. Fail-open on any
        # problem (service down, no key, no rows).
        if EVENT_BLACKOUT_HOURS > 0:
            _blackout = False
            _why = ""
            try:
                _ev = await self._http.get(
                    f"{self._config.stock_price_api_url}/stock/events/{symbol}",
                    params={"within_hours": EVENT_BLACKOUT_HOURS},
                )
                if getattr(_ev, "status_code", None) == 200:
                    _body = _ev.json()
                    if isinstance(_body, dict) and _body.get("blackout"):
                        _blackout = True
                        _rows = _body.get("events") or []
                        _why = (_rows[0].get("title") if _rows else "") or "event within blackout window"
            except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
                LOG.debug("Event blackout check failed for %s, failing open: %s", symbol, e)
            if _blackout:
                LOG.warning("Event blackout -- skipping entry for %s: %s", symbol, _why)
                return {
                    "symbol": symbol, "action": "entry_blocked_by_event_blackout",
                    "reason": _why,
                }

        # how-to-make-it-live.md #13: liquidity / spread gate. Placed after the
        # cheaper guards and the zero-size early-return (mirrors the CVaR gate's
        # position) so the quote call is one request per *real* entry attempt,
        # not per symbol per cycle. ENTRIES ONLY -- _evaluate_open_position
        # never consults it. Fail-open on any quote problem.
        if MAX_SPREAD_BPS > 0:
            _qp: Any = None
            try:
                _q = await self._http.get(
                    f"{self._config.stock_price_api_url}/stock/quote/{symbol}",
                )
                if getattr(_q, "status_code", None) == 200:
                    _qp = _q.json()
            except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
                LOG.debug("Spread gate: quote fetch failed for %s, failing open: %s", symbol, e)
            _spread = _spread_bps_from_quote(_qp)
            if _spread is not None and _spread > MAX_SPREAD_BPS:
                LOG.warning(
                    "Spread gate: %s spread %.1fbps exceeds %.1fbps -- pausing entry",
                    symbol, _spread, MAX_SPREAD_BPS,
                )
                return {
                    "symbol": symbol, "action": "entry_blocked_by_wide_spread",
                    "reason": f"spread {_spread:.1f}bps exceeds max {MAX_SPREAD_BPS:.1f}bps",
                }

        if FORECAST_SCALING_ENABLED:
            confidence = (plan.get("forecast") or {}).get("confidence")
            scale = _forecast_confidence_scale(confidence)
            if scale < 1.0:
                LOG.info(
                    "Trade plan for %s: forecast confidence %s scales size %.1f%% -> %.1f%%",
                    symbol, confidence, size_pct * 100, size_pct * scale * 100,
                )
            size_pct *= scale

        # how-to-make-it-live.md #17: dynamic vol targeting. Scales size down
        # when the plan's frozen daily vol runs above the annual target
        # (0.15). daily_vol 0.0 = not computed -> no scaling.
        if VOL_TARGET_ENABLED:
            daily_vol = risk_bands.get("daily_vol", 0.0) or 0.0
            vscale = _vol_target_scale(daily_vol)
            if vscale < 1.0:
                LOG.info(
                    "Trade plan for %s: daily vol %.4f vs target -- scaling size %.1f%% -> %.1f%%",
                    symbol, daily_vol, size_pct * 100, size_pct * vscale * 100,
                )
            size_pct *= vscale

        qty = (size_pct * portfolio_value) / price
        if qty <= 0:
            return None

        verdict, reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT -- skipping entry for %s: %s", symbol, reason)
            return {"symbol": symbol, "action": "entry_blocked_by_breaker", "reason": reason}

        locked, lock_reason = cooldown_active(self._book)
        if locked:
            LOG.warning("Cooldown -- skipping entry for %s: %s", symbol, lock_reason)
            return {"symbol": symbol, "action": "entry_blocked_by_cooldown", "reason": lock_reason}

        turb, turb_reason = await turbulence_active(self._fetch_recent_prices, symbol)
        if turb:
            LOG.warning("Turbulence -- skipping entry for %s: %s", symbol, turb_reason)
            return {"symbol": symbol, "action": "entry_blocked_by_turbulence", "reason": turb_reason}

        if direction == "short":
            # Borrow check (16): explicit not-shortable blocks, anything
            # else fails open (broker unconfigured, lookup error).
            try:
                _asset = await self._http.get(
                    f"{self._config.agent_api_url}/agent/broker/asset/{symbol}",
                )
                if _asset.status_code == 200:
                    _shortable = _asset.json().get("shortable")
                    if _shortable is False:
                        LOG.warning("Borrow -- %s not shortable, skipping short entry", symbol)
                        return {"symbol": symbol, "action": "entry_blocked_by_borrow", "reason": f"{symbol} not shortable"}
            except Exception as e:
                LOG.debug("Borrow check failed for %s, failing open: %s", symbol, e)

        side = "buy" if direction == "long" else "sell"
        pre_signed = (await self._fetch_broker_positions()).get(symbol, 0.0)
        # Stage 0 (G3): a real resting stop at the broker, not just a
        # stop_loss field inside our own book -- so an open position stays
        # protected even if this process is down. This is deliberately a
        # static, one-time CATASTROPHIC BACKSTOP, not the plan's actual exit
        # logic: the dynamic invalidation/contingency rules below (evaluated
        # every cycle against live metrics) remain the primary, tighter exit
        # mechanism and keep tightening/trailing the book's own stop_loss
        # field independently of this broker order, which is never
        # re-placed. There is no fixed stop/target price anywhere in
        # RiskBand to forward -- one has to be derived. cvar_95_limit (the
        # plan's frozen 95% daily tail-loss estimate) is the only field on
        # the plan that represents "how bad could one day plausibly be", so
        # it's what a catastrophic-only backstop should be sized from.
        # Fails open (no bracket param, same as a plain market order) when
        # it wasn't computed -- same posture as every other data-quality
        # guard in this file (CVaR gate, vol-target scaling) rather than
        # inventing an arbitrary distance.
        backstop_stop_price: float | None = None
        cvar_95_for_stop = risk_bands.get("cvar_95_limit", 0.0) or 0.0
        if cvar_95_for_stop > 0:
            backstop_stop_price = (
                price * (1 - cvar_95_for_stop) if direction == "long"
                else price * (1 + cvar_95_for_stop)
            )
        order_result = await self._submit_order(
            symbol, side, qty, stop_loss_price=backstop_stop_price,
        )
        if order_result.get("status") == "submitted":
            # how-to-make-it-live.md #15: book what actually filled, not the
            # intended qty -- a partial fill otherwise leaves every downstream
            # risk/exit/P&L calc keyed off shares the account never held.
            intended_delta = qty if direction == "long" else -qty
            actual_delta, partial = await self._confirm_fill(symbol, pre_signed, intended_delta)
            fill_qty = abs(actual_delta) or qty  # never book a zero-share position
            self._note_traded(symbol)
            with book_lock(self._book_lock_path):
                open_position(
                    self._book, symbol, direction, fill_qty, price,
                    artifact_id=plan.get("_artifact_id", ""),
                )
            if partial:
                LOG.warning(
                    "Partial fill on %s entry: intended %.4f, filled %.4f -- booked actual",
                    symbol, qty, fill_qty,
                )
            LOG.info("Entered %s %s %.4f @ %.2f", direction, symbol, fill_qty, price)
            slippage_bps = await self._entry_slippage_bps(symbol, price, direction, pre_signed)
            if slippage_bps is not None:
                LOG.info(
                    "Entry slippage %s: planned %.2f vs broker avg-entry -> %+.1f bps",
                    symbol, price, slippage_bps,
                )
            action = {
                "symbol": symbol, "action": "entered", "direction": direction,
                "qty": fill_qty, "price": price,
            }
            if slippage_bps is not None:
                action["slippage_bps"] = round(slippage_bps, 1)
            if partial:
                action.update({"partial_fill": True, "intended_qty": qty})
            return action

        LOG.info(
            "Entry not filled for %s: broker status=%s", symbol, order_result.get("status"),
        )
        return {"symbol": symbol, "action": "entry_not_filled", "broker_status": order_result.get("status")}

    # ------------------------------------------------------------------
    # Open-position evaluation
    # ------------------------------------------------------------------

    async def _fetch_calibration_accuracy(self, artifact_id: str) -> float | None:
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/trade-plan/{artifact_id}/calibration",
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            n = data.get("n_entries", 0)
            if n < 5:
                return None
            return data.get("accuracy")
        except Exception as e:
            LOG.debug("Failed to fetch calibration for %s: %s", artifact_id, e)
        return None

    async def _evaluate_open_position(
        self, plan: dict[str, Any], position: Position, price: float, portfolio_value: float,
    ) -> dict[str, Any] | None:
        symbol = position.symbol
        # how-to-make-it-live.md #16: a stale feed does NOT block managing an
        # open position -- an exit/reduce on a slightly stale mark still beats
        # flying blind. Surface it so it is visible in the logs, then proceed.
        if PRICE_MAX_AGE_HOURS > 0:
            _age = _price_ts_age_hours(self._last_price_ts.get(symbol))
            if _age is not None and _age > PRICE_MAX_AGE_HOURS:
                LOG.warning(
                    "Price feed for %s is %.1fh stale (max %.1fh) -- evaluating "
                    "open position anyway (exits are never gated on freshness)",
                    symbol, _age, PRICE_MAX_AGE_HOURS,
                )
        previous_close = self._last_prices.get(symbol)
        recent_prices = await self._fetch_recent_prices(symbol)
        recent_returns = _simple_returns(recent_prices)
        cluster_corr = await self._fetch_shock_cluster_correlation(symbol)

        artifact_id = plan.get("_artifact_id", "")
        calibration_accuracy = await self._fetch_calibration_accuracy(artifact_id) if artifact_id else None

        created_at = plan.get("created_at", "")
        days_elapsed = 0
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                days_elapsed = (datetime.now(timezone.utc) - created).days
            except (ValueError, TypeError):
                pass

        metrics = compute_live_metrics(
            position, price, plan,
            recent_returns=recent_returns,
            previous_close=previous_close,
            shock_cluster_correlation=cluster_corr,
            calibration_accuracy=calibration_accuracy,
            days_elapsed=days_elapsed,
        )

        # Time-stop (15 step2): loser sits forever without invalidation.
        # Auto exit on max_hold_days expiry with reason time_stop. Risk-reducing, allowed on HALT entries-only.
        age_days = _position_age_days(position.opened_at)
        if MAX_HOLD_DAYS > 0 and age_days > MAX_HOLD_DAYS:
            LOG.info("Time-stop expiry for %s -- age %dd > max %dd", symbol, age_days, MAX_HOLD_DAYS)
            return await self._apply_invalidation(
                position, price, portfolio_value,
                {"condition": f"time_stop age {age_days}d > max {MAX_HOLD_DAYS}d", "action": "exit"},
            )

        triggered_invalidations = find_triggered_rules(
            plan.get("invalidation_conditions") or [], metrics,
        )
        if triggered_invalidations:
            return await self._apply_invalidation(
                position, price, portfolio_value, triggered_invalidations[0],
            )

        triggered_contingencies = find_triggered_rules(
            plan.get("contingency_rules") or [], metrics,
        )
        if triggered_contingencies:
            return await self._apply_contingency(
                position, price, portfolio_value, triggered_contingencies[0],
            )

        rebalance_request = self._rebalance_queue.pending_for(symbol)
        if rebalance_request is not None:
            return await self._evaluate_rebalance_request(
                position, price, portfolio_value, rebalance_request, recent_returns=recent_returns,
            )

        # Trailing 2x ATR (15 step2): ratchet stop up for longs (down for
        # shorts), never loosen. Best-effort, never blocks hold.
        try:
            _new_stop = trailing_stop_for(position, price, recent_prices)
            if _new_stop is not None:
                _old = getattr(position, "stop_loss", None)
                _side = str(getattr(position, "side", getattr(position, "direction", "long"))).lower()
                if _side in ("short", "sell"):
                    _ratchet = _old is None or _new_stop < _old
                else:
                    _ratchet = _old is None or _new_stop > _old
                if _ratchet:
                    from vinu_live.book.positions import update_stop_loss as _update_sl

                    _update_sl(self._book, position.position_id, _new_stop)
                    LOG.info("Trailing stop ratchet %s: %s -> %s", symbol, _old, round(_new_stop, 2))
        except Exception as e:
            LOG.debug("Trailing ratchet failed for %s: %s", symbol, e)

        # Bracket 50% at 1R (15 step3): risk = |entry - stop|, gain at least
        # 1R and no partial taken yet -> reduce half. Needs a real stop;
        # without one there is no R to measure against, so skip (honest).
        # Risk-reducing, allowed on HALT entries-only.
        try:
            _stop = getattr(position, "stop_loss", None)
            _taken = bool(getattr(position, "partial_taken", False))
            if _stop and not _taken and position.avg_entry > 0:
                _is_long = str(getattr(position, "side", "long")).lower() not in ("short", "sell")
                _risk = abs(position.avg_entry - _stop)
                _gain = (price - position.avg_entry) if _is_long else (position.avg_entry - price)
                if _risk > 0 and _gain >= _risk:
                    _bracket_qty = position.qty * 0.5
                    _bracket_side = "sell" if _is_long else "buy"
                    _bracket_res = await self._submit_order(symbol, _bracket_side, _bracket_qty, reduce_only=True)
                    if _bracket_res.get("status") == "submitted":
                        from vinu_live.book.positions import reduce_position as _reduce_pos

                        _reduce_pos(self._book, position.position_id, _bracket_qty, price)
                        LOG.info("Bracket 1R partial for %s: reduced %.4f @ %.2f", symbol, _bracket_qty, price)
                        return {"symbol": symbol, "action": "bracket_partial", "qty": _bracket_qty, "price": price}
        except Exception as e:
            LOG.debug("Bracket partial failed for %s: %s", symbol, e)

        LOG.info("No rule triggered for %s -- holding unchanged", symbol)
        return {"symbol": symbol, "action": "hold", "reason": "no_rule_triggered"}

    # 2026-09-11 reasoning-audit fix (the-reasoning-inefficiency/00-audit.md
    # item C1a): a FLAT gain-protect percent meant "5%" was treated as an
    # equally real, equally protect-worthy move on a name that swings 1%/day
    # and one that swings 8%/day -- the exact "number disconnected from what
    # it's supposed to represent" gap that audit exists to close. Now scaled
    # by the position's own realized daily volatility (the same
    # pstdev-of-recent-returns measure turbulence_active() already uses,
    # data the caller already computed for this exact cycle -- no new fetch,
    # no live trading history needed to derive this). `_REBALANCE_PROTECT_GAIN_PCT`
    # remains as the documented fail-open floor for when there isn't enough
    # price history to compute a real volatility figure -- an unmeasurable
    # move still needs *some* protection, and a fixed conservative floor
    # beats treating "no data" as "protect nothing."
    _REBALANCE_PROTECT_GAIN_PCT = 0.05
    _REBALANCE_PROTECT_VOL_MULTIPLE = 2.0
    _REBALANCE_PROTECT_MIN_RETURNS = 5

    async def _evaluate_rebalance_request(
        self, position: Position, price: float, portfolio_value: float, request: Any,
        *, recent_returns: list[float] | None = None,
    ) -> dict[str, Any]:
        """The rebalance request is advisory input ONLY -- this method is
        reached exclusively when the plan's own real invalidation/
        contingency rules found nothing to act on (see
        _evaluate_open_position above). It can still decline: a real
        unrealized gain beyond the (volatility-scaled) protect threshold is
        a real reason to hold, not honor the request, matching
        02-guard-rail.md's 'orchestrator retains final say.'"""
        symbol = position.symbol
        self._rebalance_queue.consume(symbol)  # considered once, either way

        favorable_move_pct = (
            (price - position.avg_entry) / position.avg_entry if position.side == "long"
            else (position.avg_entry - price) / position.avg_entry
        ) if position.avg_entry > 0 else 0.0

        protect_threshold = self._REBALANCE_PROTECT_GAIN_PCT
        if recent_returns and len(recent_returns) >= self._REBALANCE_PROTECT_MIN_RETURNS:
            import statistics as _st

            realized_vol = _st.pstdev(recent_returns[-14:])
            if realized_vol > 0:
                protect_threshold = self._REBALANCE_PROTECT_VOL_MULTIPLE * realized_vol

        is_critical = getattr(request, "critical", False)
        if favorable_move_pct > protect_threshold and not is_critical:
            LOG.info(
                "Declining rebalance request for %s -- unrealized gain %.2f%% protects the "
                "position (threshold %.2f%%)", symbol, favorable_move_pct * 100, protect_threshold * 100,
            )
            return {
                "symbol": symbol, "action": "rebalance_declined",
                "reason": request.reason, "unrealized_gain_pct": favorable_move_pct,
                "protect_threshold_pct": protect_threshold,
            }
        if is_critical and favorable_move_pct > protect_threshold:
            LOG.warning(
                "Rebalance request for %s is CRITICAL -- overriding the %.2f%% gain-protect "
                "(unrealized gain %.2f%%)", symbol, protect_threshold * 100,
                favorable_move_pct * 100,
            )

        verdict, breaker_reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT -- skipping rebalance reduce for %s: %s", symbol, breaker_reason)
            return {"symbol": symbol, "action": "rebalance_blocked_by_breaker", "reason": breaker_reason}

        reduce_qty = position.qty * 0.5
        side = "sell" if position.side == "long" else "buy"
        order_result = await self._submit_order(symbol, side, reduce_qty, reduce_only=True)
        if order_result.get("status") == "submitted":
            reduce_position(self._book, position.position_id, reduce_qty, price)
            LOG.info("Honored rebalance request for %s (reason: %s)", symbol, request.reason)
            return {
                "symbol": symbol, "action": "rebalance_honored",
                "qty": reduce_qty, "reason": request.reason, "critical": is_critical,
            }

        LOG.info("Rebalance reduce not filled for %s: broker status=%s", symbol, order_result.get("status"))
        return {
            "symbol": symbol, "action": "rebalance_not_filled",
            "broker_status": order_result.get("status"), "reason": request.reason,
        }

    async def _apply_invalidation(
        self, position: Position, price: float, portfolio_value: float, rule: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = position.symbol
        verdict, reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT and not _halt_allows_exit():
            LOG.warning("Breaker HALT -- skipping invalidation exit for %s: %s", symbol, reason)
            return {"symbol": symbol, "action": "exit_blocked_by_breaker", "reason": reason, "rule": rule}
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT entries-only -- allowing risk-reducing exit for %s: %s", symbol, reason)

        # Close against the LIVE broker holding, not the (possibly stale) book
        # qty -- observed live: a reduce_only SELL for the book qty on an
        # already-flat account opened a short.
        close_qty, close_side, note = await self._broker_close_plan(
            symbol, position.side, position.qty,
        )
        if note == "broker_flat":
            with book_lock(self._book_lock_path):
                close_position(self._book, position.position_id, price)
            LOG.warning(
                "Invalidation exit %s: broker already flat -- closed stale book position, no order",
                symbol,
            )
            return {"symbol": symbol, "action": "invalidation_exit_book_only", "reason": "broker_flat", "rule": rule}
        if note == "side_conflict":
            LOG.error(
                "Invalidation exit %s: broker holds the OPPOSITE side -- not trading (needs review)",
                symbol,
            )
            return {"symbol": symbol, "action": "exit_blocked_side_conflict", "rule": rule}

        order_result = await self._submit_order(symbol, close_side, close_qty, reduce_only=True)
        if order_result.get("status") == "submitted":
            self._note_traded(symbol)
            with book_lock(self._book_lock_path):
                close_position(self._book, position.position_id, price)
            LOG.info("Invalidation exit for %s %.4f (rule: %s)", symbol, close_qty, rule.get("condition"))
            return {"symbol": symbol, "action": "invalidation_exit", "qty": close_qty, "rule": rule}

        LOG.info("Invalidation exit not filled for %s: broker status=%s", symbol, order_result.get("status"))
        return {"symbol": symbol, "action": "exit_not_filled", "broker_status": order_result.get("status"), "rule": rule}

    async def _apply_contingency(
        self, position: Position, price: float, portfolio_value: float, rule: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = position.symbol
        action = rule.get("action")
        params = rule.get("action_params") or {}

        if action == "tighten_stop":
            tighten_pct = params.get("tighten_by_pct", 0.3)
            favorable_move = (price - position.avg_entry) if position.side == "long" else (position.avg_entry - price)
            offset = max(favorable_move, 0.0) * tighten_pct
            new_stop = price - offset if position.side == "long" else price + offset
            update_stop_loss(self._book, position.position_id, new_stop)
            LOG.info("Tightened stop for %s to %.2f (rule: %s)", symbol, new_stop, rule.get("condition"))
            return {"symbol": symbol, "action": "tighten_stop", "new_stop": new_stop, "rule": rule}

        if action == "reduce_position":
            reduce_pct = params.get("reduce_by_pct", 0.5)
            reduce_qty = position.qty * reduce_pct
            verdict, reason = await self._check_breaker(portfolio_value)
            if verdict == BreakerVerdict.HALT and not _halt_allows_exit():
                LOG.warning("Breaker HALT -- skipping reduce for %s: %s", symbol, reason)
                return {"symbol": symbol, "action": "reduce_blocked_by_breaker", "reason": reason, "rule": rule}

            close_qty, close_side, note = await self._broker_close_plan(
                symbol, position.side, reduce_qty,
            )
            if note == "broker_flat":
                with book_lock(self._book_lock_path):
                    close_position(self._book, position.position_id, price)
                LOG.warning("Reduce %s: broker flat -- closed stale book position, no order", symbol)
                return {"symbol": symbol, "action": "reduce_book_only", "reason": "broker_flat", "rule": rule}
            if note == "side_conflict":
                LOG.error("Reduce %s: broker holds the OPPOSITE side -- not trading (needs review)", symbol)
                return {"symbol": symbol, "action": "reduce_blocked_side_conflict", "rule": rule}

            order_result = await self._submit_order(symbol, close_side, close_qty, reduce_only=True)
            if order_result.get("status") == "submitted":
                self._note_traded(symbol)
                with book_lock(self._book_lock_path):
                    reduce_position(self._book, position.position_id, close_qty, price)
                LOG.info("Reduced %s by %.4f (rule: %s)", symbol, close_qty, rule.get("condition"))
                return {"symbol": symbol, "action": "reduce_position", "qty": close_qty, "rule": rule}

            LOG.info("Reduce not filled for %s: broker status=%s", symbol, order_result.get("status"))
            return {"symbol": symbol, "action": "reduce_not_filled", "broker_status": order_result.get("status"), "rule": rule}

        LOG.warning(
            "Unhandled contingency action %r for %s -- no matching handler, holding "
            "unchanged (explicit, not a silent no-op)", action, symbol,
        )
        return {"symbol": symbol, "action": "unhandled_contingency", "rule": rule}

    # ------------------------------------------------------------------
    # Breaker
    # ------------------------------------------------------------------

    async def _check_breaker(self, portfolio_value: float) -> tuple[str, str | None]:
        positions = list_open_positions(self._book)
        symbols = sorted({p.symbol for p in positions})
        prices = await self._fetch_prices(symbols) if symbols else {}
        daily_pnl = daily_realized_pnl(self._book)
        covariance_matrix = await self._compute_covariance(symbols) if len(symbols) >= 2 else None
        return check_limits(
            self._book,
            prices=prices,
            portfolio_value=portfolio_value,
            daily_realized_pnl=daily_pnl,
            covariance_matrix=covariance_matrix,
            cluster_map=None,
            state=self._breaker_state,
        )

    async def _compute_covariance(self, symbols: list[str]) -> np.ndarray | None:
        from vinu_tools.compute.risk.covariance import dynamic_covariance

        price_series = await asyncio.gather(*(self._fetch_recent_prices(s) for s in symbols))
        min_len = min((len(p) for p in price_series), default=0)
        if min_len < 20:
            return None
        aligned = np.array([p[-min_len:] for p in price_series])
        cov = dynamic_covariance(aligned, window=_COVARIANCE_WINDOW, use_shrinkage=True)
        if np.any(np.isnan(cov)):
            return None
        return cov

    async def _check_runtime_correlation(self, prices: dict[str, float]) -> dict[str, Any]:
        """how-to-make-it-live.md #12: once per cycle, look at the DCC/shrinkage
        correlation between the positions actually open and reduce_only-trim the
        larger side of any pair moving dangerously together in the direction the
        book is exposed. reduce_only => can only cut risk. Per-symbol cooldown."""
        if not RUNTIME_CORR_ENABLED:
            return {"checked": False, "reason": "disabled"}
        positions = list_open_positions(self._book)
        symbols = sorted({p.symbol for p in positions})
        if len(symbols) < 2:
            return {"checked": False, "reason": "fewer than 2 symbols open"}

        cov = await self._compute_covariance(symbols)
        if cov is None:
            return {"checked": False, "reason": "covariance unavailable"}
        from vinu_tools.compute.risk.covariance import correlation_from_covariance

        corr = correlation_from_covariance(cov)
        idx = {sym: i for i, sym in enumerate(symbols)}

        # Net signed exposure + gross market value per symbol.
        signed: dict[str, float] = {}
        mv: dict[str, float] = {}
        for p in positions:
            s = 1.0 if p.side == "long" else -1.0
            px = prices.get(p.symbol) or p.avg_entry
            signed[p.symbol] = signed.get(p.symbol, 0.0) + s
            mv[p.symbol] = mv.get(p.symbol, 0.0) + abs(p.qty) * px

        now = time.monotonic()
        threshold = runtime_corr_threshold()
        reduce_pct = runtime_corr_reduce_pct()
        cooldown_sec = runtime_corr_cooldown_sec()
        flagged: list[dict[str, Any]] = []
        reductions: list[dict[str, Any]] = []
        for a, b in ((symbols[i], symbols[j]) for i in range(len(symbols)) for j in range(i + 1, len(symbols))):
            sa, sb = float(np.sign(signed.get(a, 0.0))), float(np.sign(signed.get(b, 0.0)))
            if sa == 0.0 or sb == 0.0:
                continue  # a symbol whose own positions net flat -- nothing to trim
            c = float(corr[idx[a], idx[b]])
            comovement = c * sa * sb  # co-movement in the direction we're exposed
            if comovement < threshold:
                continue
            flagged.append({"pair": [a, b], "correlation": round(c, 3), "comovement": round(comovement, 3)})

            target = a if mv.get(a, 0.0) >= mv.get(b, 0.0) else b
            # Bug found 2026-09-10: 0.0 as the "never reduced" sentinel
            # assumed time.monotonic() starts near zero. It doesn't -- the
            # reference point is implementation-defined (often process/
            # system start), so on a freshly booted host `now` itself can
            # be smaller than RUNTIME_CORR_COOLDOWN_SEC, making
            # `now - 0.0 < COOLDOWN` true and silently blocking the very
            # first reduction a process would ever make. None means "no
            # prior record" unambiguously; only compare elapsed time when
            # there actually is a prior record.
            last_reduce = self._last_corr_reduce.get(target)
            if last_reduce is not None and now - last_reduce < cooldown_sec:
                continue
            pos = self._find_open_position(target)
            if pos is None:
                continue
            reduce_qty = pos.qty * reduce_pct
            if reduce_qty <= 0:
                continue
            price = prices.get(target) or pos.avg_entry
            side = "sell" if pos.side == "long" else "buy"
            order_result = await self._submit_order(target, side, reduce_qty, reduce_only=True)
            if order_result.get("status") == "submitted":
                self._note_traded(target)
                with book_lock(self._book_lock_path):
                    reduce_position(self._book, pos.position_id, reduce_qty, price)
                self._last_corr_reduce[target] = now
                LOG.warning(
                    "Runtime correlation: %s~%s corr %.2f (comovement %.2f >= %.2f) -- "
                    "reduced %s by %.0f%% (%.4f)",
                    a, b, c, comovement, threshold, target,
                    reduce_pct * 100, reduce_qty,
                )
                reductions.append({
                    "symbol": target, "pair": [a, b],
                    "correlation": round(c, 3), "reduce_qty": reduce_qty,
                })
            else:
                LOG.info(
                    "Runtime correlation reduce for %s not filled: %s",
                    target, order_result.get("status"),
                )
        return {"checked": True, "n_flagged_pairs": len(flagged), "flagged": flagged, "reductions": reductions}

    async def _check_ood(self, prices: dict[str, float]) -> dict[str, Any]:
        """how-to-make-it-live.md #33 part 2: out-of-distribution detector.
        Scores the open book against three fail-open signals; fires only when
        >= OOD_MIN_SIGNALS trip together. Action is set by VINU_LIVE_OOD_DETECTOR
        (off | alert | halt | flatten). Latched via self._ood_acted so an
        auto-action happens at most once per process."""
        if OOD_DETECTOR_MODE not in ("alert", "halt", "flatten"):
            return {"checked": False, "reason": "disabled"}

        positions = list_open_positions(self._book)
        symbols = sorted({p.symbol for p in positions})
        if not symbols:
            return {"checked": False, "reason": "no open positions"}

        import statistics as _st

        signals: list[str] = []
        detail: dict[str, Any] = {}

        # 1. crisis correlation -- mean |pairwise corr| across the open book
        if len(symbols) >= 2:
            cov = await self._compute_covariance(symbols)
            if cov is not None:
                from vinu_tools.compute.risk.covariance import correlation_from_covariance

                corr = correlation_from_covariance(cov)
                offdiag = [
                    abs(float(corr[i, j]))
                    for i in range(len(symbols))
                    for j in range(i + 1, len(symbols))
                ]
                if offdiag:
                    mean_abs_corr = sum(offdiag) / len(offdiag)
                    detail["mean_abs_corr"] = round(mean_abs_corr, 3)
                    if mean_abs_corr >= OOD_CORR_THRESHOLD:
                        signals.append(
                            f"crisis_correlation {mean_abs_corr:.2f}>={OOD_CORR_THRESHOLD:.2f}"
                        )

        # 2 + 3. recent per-symbol returns -> vol explosion + single-day gap
        series = await asyncio.gather(*(self._fetch_recent_prices(s) for s in symbols))
        vols: list[float] = []
        max_move = 0.0
        for closes in series:
            rets = _simple_returns(closes)
            if len(rets) >= 5:
                window = rets[-14:] if len(rets) >= 14 else rets
                vols.append(_st.pstdev(window))
            if rets:
                max_move = max(max_move, abs(rets[-1]))
        if vols:
            mean_vol = sum(vols) / len(vols)
            detail["mean_realized_vol"] = round(mean_vol, 4)
            if mean_vol >= OOD_VOL_THRESHOLD:
                signals.append(f"vol_explosion {mean_vol:.3f}>={OOD_VOL_THRESHOLD:.3f}")
        detail["max_1d_move"] = round(max_move, 4)
        if max_move >= OOD_MOVE_THRESHOLD:
            signals.append(f"gap_move {max_move:.2f}>={OOD_MOVE_THRESHOLD:.2f}")

        # 4. turbulence -- Mahalanobis distance of today's joint return
        # vector from its recent trailing distribution, against the same
        # `cov` signal 1 already built. Reuses the return series already
        # fetched above; adds one small linear-algebra op, no extra I/O.
        # `cov` is bound (to a matrix or None) whenever len(symbols) >= 2,
        # since signal 1 above runs under that same condition.
        if len(symbols) >= 2 and OOD_TURBULENCE_MULT > 0 and cov is not None:
            _rows = [_simple_returns(c) for c in series]
            if len(_rows) == len(symbols) and all(len(r) >= 15 for r in _rows):
                _arr = np.array([r[-14:] for r in _rows])  # (n_symbols, 14)
                _today = _arr[:, -1]
                _hist_mean = _arr[:, :-1].mean(axis=1)
                try:
                    _diff = _today - _hist_mean
                    _md2 = float(_diff @ np.linalg.pinv(cov) @ _diff)
                    detail["turbulence_md2"] = round(_md2, 2)
                    _thresh = OOD_TURBULENCE_MULT * len(symbols)
                    if _md2 >= _thresh:
                        signals.append(f"turbulence md2 {_md2:.1f}>={_thresh:.1f}")
                except Exception as _e:  # noqa: BLE001 -- fail-open, same as every other OOD signal
                    LOG.debug("turbulence signal skipped: %s", _e)

        triggered = len(signals) >= OOD_MIN_SIGNALS
        result: dict[str, Any] = {
            "checked": True,
            "mode": OOD_DETECTOR_MODE,
            "signals": signals,
            "signal_count": len(signals),
            "min_signals": OOD_MIN_SIGNALS,
            "triggered": triggered,
            "detail": detail,
            "acted": False,
        }
        if not triggered:
            return result

        LOG.warning(
            "OOD detector TRIGGERED (%d/%d signals): %s",
            len(signals), OOD_MIN_SIGNALS, "; ".join(signals),
        )

        if OOD_DETECTOR_MODE == "alert":
            result["note"] = "alert-only -- no action taken"
            return result
        if self._ood_acted:
            result["note"] = "already acted this process lifetime -- no repeat action"
            return result

        reason = f"auto-OOD [{'; '.join(signals)}]"
        if OOD_DETECTOR_MODE == "flatten":
            flat = await self.emergency_flatten(reason=reason)
            result["action"] = "emergency_flatten"
            result["flatten_result"] = flat
            result["acted"] = True
        else:  # halt
            ok = False
            try:
                resp = await self._http.post(
                    f"{self._config.agent_api_url}/agent/broker/halt",
                    json={"reason": reason},
                )
                ok = getattr(resp, "status_code", None) == 200
            except Exception as e:  # noqa: BLE001
                LOG.error("OOD halt call failed: %s", e)
            if ok:
                self._trading_halted = True
                self._breaker_state.halted = True
                self._breaker_state.halted_at = datetime.now(timezone.utc).isoformat()
                self._breaker_state.halted_reason = reason
            result["action"] = "halt"
            result["acted"] = ok

        self._ood_acted = self._ood_acted or bool(result["acted"])
        return result

    # ------------------------------------------------------------------
    # Broker / market data
    # ------------------------------------------------------------------

    def _find_open_position(self, symbol: str) -> Position | None:
        positions = list_open_positions(self._book, symbol=symbol)
        return positions[0] if positions else None

    def _note_traded(self, symbol: str) -> None:
        """Stamp `symbol` as just-traded by this instance (fill-propagation
        grace for _reconcile_book_with_broker -- see RECONCILE_SETTLE_SEC)."""
        self._recently_traded[symbol] = time.monotonic()

    async def _broker_close_plan(
        self, symbol: str, book_side: str, book_qty: float,
    ) -> tuple[float, str, str]:
        """How to actually close a book position against the LIVE broker
        holding -- never asking the broker to trade more than it holds, and
        never flipping a flat / opposite account into a NEW position (observed
        live: a reduce_only SELL for the book qty on an already-flat account
        opened a short). Returns (qty_to_send, order_side, note):
          "ok"             -> place an order for qty_to_send on order_side
          "broker_flat"    -> broker holds nothing; send nothing, just fix book
          "side_conflict"  -> broker holds the OTHER side; send nothing, alert
          "no_broker_view" -> broker unreadable; fall back to the book qty
        """
        try:
            broker = await self._fetch_broker_positions()
        except Exception:  # noqa: BLE001
            broker = {}
        fallback_side = "sell" if book_side == "long" else "buy"
        if not broker:
            return float(book_qty), fallback_side, "no_broker_view"
        bq = float(broker.get(symbol, 0.0))
        if abs(bq) <= 1e-9:
            return 0.0, "", "broker_flat"
        book_signed = book_qty if book_side == "long" else -book_qty
        if bq * book_signed < 0:
            return 0.0, "", "side_conflict"
        return min(float(book_qty), abs(bq)), ("sell" if bq > 0 else "buy"), "ok"

    async def _submit_order(
        self, symbol: str, side: str, qty: float, artifact_id: str = "", reduce_only: bool = False,
        stop_loss_price: float | None = None,
    ) -> dict[str, Any]:
        # Idempotency (16 step8): client_order_id = artifact+symbol+side+qty+minute bucket.
        # Retry within same minute dedupes on broker, no double fill.
        #
        # Stage 1 (how-to-make-it-live.md): this was previously computed and
        # sent but silently dropped -- OrderRequest (vinu-agent's HTTP
        # schema) had no client_order_id field, so it never reached Alpaca
        # and the dedup never actually happened. Fixed at the OrderRequest /
        # TradeTool / AlpacaBroker layer; this call site is unchanged.
        import os as _os

        if _os.environ.get("VINU_EXEC_IDEMPOTENCY_ENABLED", "true").lower() not in ("1", "true", "yes"):
            client_order_id = ""
        else:
            import time as _time

            bucket = int(_time.time() // 60)
            base = artifact_id or "no-artifact"
            client_order_id = f"{base}-{symbol}-{side}-{qty:.4f}-{bucket}"
        try:
            payload: dict[str, Any] = {
                "symbol": symbol, "side": side, "qty": qty, "order_type": "market",
                "reduce_only": reduce_only,
            }
            if client_order_id:
                payload["client_order_id"] = client_order_id
            # Stage 0 (G3): a catastrophic-backstop stop price, when the caller
            # supplied one (see _maybe_enter). AlpacaBroker.submit_order()
            # attaches it as a real resting order_class="oto" stop leg -- never
            # combined with a take-profit here, so it's always the "oto"
            # single-leg case, not "bracket". reduce_only orders (exits) never
            # pass this -- a stop on a stop would be nonsensical.
            if stop_loss_price is not None:
                payload["stop_loss_price"] = stop_loss_price
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/broker/order",
                json=payload,
            )
            if resp.status_code != 200:
                return {"status": "error", "http_status": resp.status_code}
            return resp.json()
        except Exception as e:
            LOG.warning("Order submission failed for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    async def _fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol in symbols:
            try:
                resp = await self._http.get(
                    f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                    params={"interval": "1d", "days": 5, "adjusted": True},
                )
                if resp.status_code == 200:
                    bars = resp.json().get("data", [])
                    if bars:
                        prices[symbol] = float(bars[-1].get("close", 0.0))
                        _parsed_ts: float | None = None
                        _bt = bars[-1].get("bar_ts")
                        if _bt is not None:
                            try:
                                _parsed_ts = float(_bt)
                            except (TypeError, ValueError):
                                _parsed_ts = None
                        if _parsed_ts is not None:
                            self._last_price_ts[symbol] = _parsed_ts
                        else:
                            # fresh price but no usable timestamp -- drop any
                            # prior ts so the freshness guard fails open rather
                            # than blocking on a lingering old value.
                            self._last_price_ts.pop(symbol, None)
            except Exception as e:
                LOG.warning("Could not fetch price for %s: %s", symbol, e)
        return prices

    async def _fetch_recent_prices(self, symbol: str, days: int = _RETURNS_LOOKBACK_DAYS) -> list[float]:
        try:
            resp = await self._http.get(
                f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "days": days, "adjusted": True},
            )
            if resp.status_code == 200:
                bars = resp.json().get("data", [])
                return [float(b["close"]) for b in bars if b.get("close")]
        except Exception as e:
            LOG.warning("Could not fetch recent prices for %s: %s", symbol, e)
        return []

    async def _fetch_portfolio_value(self) -> float:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
            if resp.status_code == 200:
                account = resp.json()
                if account.get("configured") and account.get("equity") is not None:
                    return float(account["equity"])
        except Exception as e:
            LOG.warning("Could not fetch account equity: %s", e)
        LOG.warning(
            "No broker account configured -- using fallback_portfolio_value=%.2f",
            self._config.fallback_portfolio_value,
        )
        return self._config.fallback_portfolio_value

    async def _fetch_shock_cluster_correlation(self, symbol: str) -> float | None:
        try:
            resp = await self._http.get(
                f"{self._config.initial_analysis_api_url}/analysis/angle/shock_clustering/{symbol}",
            )
            if resp.status_code != 200:
                return None
            rows = resp.json().get("data", [])
            if not rows:
                return None
            members = (rows[-1] or {}).get("cluster_members") or []
            correlations = [abs(m.get("shock_correlation", 0.0)) for m in members]
            return max(correlations) if correlations else None
        except Exception as e:
            LOG.warning("Could not fetch shock cluster correlation for %s: %s", symbol, e)
            return None

    # ------------------------------------------------------------------
    # Emergency flatten — how-to-make-it-live.md #33 (Stage 4), panic switch
    # ------------------------------------------------------------------

    async def _is_trading_halted(self) -> bool:
        """Read the agent's global kill switch (filesystem-backed,
        cross-process). Fail-safe here is False: if the agent is unreachable
        no order can be placed anyway, the broker-outage guard covers that,
        and a real halt file is simply re-read next cycle."""
        try:
            resp = await self._http.get(
                f"{self._config.agent_api_url}/agent/broker/status",
            )
            if getattr(resp, "status_code", None) == 200:
                return bool((resp.json() or {}).get("halted"))
        except Exception as e:  # noqa: BLE001
            LOG.debug("Halt-status check failed, treating as not-halted: %s", e)
        return False

    async def emergency_flatten(self, reason: str = "manual") -> dict[str, Any]:
        """The panic switch (how-to-make-it-live.md #33). Two steps:
        (1) set the agent's global kill switch so NO service can place a new
            order (OrderGuard rejects on it; reduce_only exits stay allowed);
        (2) submit a reduce_only market close for every open book position.
        A position whose close does not confirm is left in the book -- the
        next cycle's _reconcile_book_with_broker pulls it straight. Undo is
        deliberate and separate: emergency_resume()."""
        LOG.warning("EMERGENCY FLATTEN requested (reason=%s)", reason)
        halted = False
        halt_error = ""
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/broker/halt",
                json={"reason": f"emergency_flatten: {reason}"},
            )
            halted = getattr(resp, "status_code", None) == 200
            if not halted:
                halt_error = f"halt returned http {getattr(resp, 'status_code', '?')}"
        except Exception as e:  # noqa: BLE001
            halt_error = str(e)
        if halted:
            self._trading_halted = True
            self._breaker_state.halted = True
            self._breaker_state.halted_at = datetime.now(timezone.utc).isoformat()
            self._breaker_state.halted_reason = f"emergency_flatten: {reason}"
        else:
            LOG.error("EMERGENCY FLATTEN: global halt did NOT engage (%s) -- "
                      "still attempting to close positions", halt_error)

        positions = list_open_positions(self._book)
        prices: dict[str, float] = {}
        if positions:
            prices = await self._fetch_prices(sorted({p.symbol for p in positions}))

        closed: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for pos in positions:
            px = prices.get(pos.symbol) or float(pos.avg_entry)
            row: dict[str, Any] = {"symbol": pos.symbol, "side": pos.side, "qty": float(pos.qty)}
            # Close against the LIVE broker holding -- never over-ask (Alpaca
            # 403s a reduce_only for more than held) and never sell into a flat
            # account (that opens a short).
            close_qty, close_side, note = await self._broker_close_plan(
                pos.symbol, pos.side, pos.qty,
            )
            if note == "broker_flat":
                with book_lock(self._book_lock_path):
                    close_position(self._book, pos.position_id, px)
                row["note"] = "broker_flat_book_closed"
                closed.append(row)
                LOG.warning("Emergency flatten: %s broker already flat -- closed stale book position", pos.symbol)
                continue
            if note == "side_conflict":
                row["note"] = "side_conflict_not_traded"
                failed.append(row)
                LOG.error("Emergency flatten: %s broker holds the OPPOSITE side -- NOT trading (needs review)", pos.symbol)
                continue
            order_result = await self._submit_order(
                pos.symbol, close_side, close_qty, artifact_id=pos.artifact_id, reduce_only=True,
            )
            if order_result.get("status") == "submitted":
                self._note_traded(pos.symbol)
                with book_lock(self._book_lock_path):
                    close_position(self._book, pos.position_id, px)
                row["qty"] = close_qty
                closed.append(row)
                LOG.warning("Emergency flatten: closed %s %s %.4f", pos.side, pos.symbol, close_qty)
            else:
                row["broker_status"] = order_result.get("status")
                failed.append(row)
                LOG.error("Emergency flatten: FAILED to close %s -- %s", pos.symbol, order_result)

        return {
            "status": "ok" if (halted and not failed) else "partial",
            "reason": reason,
            "halted": halted,
            "halt_error": halt_error,
            "positions_closed": closed,
            "positions_failed": failed,
            "count_closed": len(closed),
            "count_failed": len(failed),
        }

    async def emergency_resume(self, reason: str = "manual") -> dict[str, Any]:
        """Lift the global kill switch set by emergency_flatten() or a manual
        halt. Does NOT reopen anything -- normal cycles just resume trading.
        Deliberately a separate, explicit action."""
        LOG.warning("EMERGENCY RESUME requested (reason=%s)", reason)
        resumed = False
        err = ""
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/broker/resume", json={},
            )
            resumed = getattr(resp, "status_code", None) == 200
            if not resumed:
                err = f"resume returned http {getattr(resp, 'status_code', '?')}"
        except Exception as e:  # noqa: BLE001
            err = str(e)
        if resumed:
            self._trading_halted = False
            self._breaker_state.reset()
        return {
            "status": "ok" if resumed else "error",
            "resumed": resumed, "error": err, "reason": reason,
        }

    async def emergency_status(self) -> dict[str, Any]:
        """Current halt state + how many positions would a flatten touch."""
        halted = await self._is_trading_halted()
        return {
            "halted": halted,
            "local_breaker_halted": self._breaker_state.halted,
            "open_positions": len(list_open_positions(self._book)),
        }

    # ------------------------------------------------------------------
    # Broker health — how-to-make-it-live.md #14 (Stage 4), outage pause
    # ------------------------------------------------------------------

    async def _check_broker_health(self) -> dict[str, Any]:
        """One /agent/broker/account liveness probe per cycle. A healthy 200
        stamps a monotonic clock and clears self._broker_degraded; a non-200 /
        transport error that persists past BROKER_STALE_SEC since the last
        healthy probe sets it. _maybe_enter pauses ENTRIES while degraded;
        exits are never gated. Returns a small status dict for the cycle
        result. Fail-safe direction: when in doubt about the broker, stop
        opening -- but a single blip inside the grace window does not pause."""
        if BROKER_STALE_SEC <= 0:
            self._broker_degraded = False
            return {"enabled": False, "degraded": False}

        ok = False
        detail = ""
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
            if getattr(resp, "status_code", None) == 200:
                body = resp.json() or {}
                # Reachable-but-unconfigured is a deployment state, not an
                # outage (_fetch_portfolio_value already logs it) -- still a
                # healthy probe here.
                ok = True
                detail = "configured" if body.get("configured") else "reachable_unconfigured"
            else:
                detail = f"http {getattr(resp, 'status_code', '?')}"
        except Exception as e:  # noqa: BLE001 -- any transport error = not healthy
            detail = f"error: {e}"

        now = time.monotonic()
        if ok:
            self._broker_ok_at = now
            if self._broker_degraded:
                LOG.warning("Broker health recovered (%s) -- entries resume", detail)
            self._broker_degraded = False
            return {"enabled": True, "degraded": False, "detail": detail}

        # 0.0 = the broker has never answered since this worker started; a
        # failed probe on top of that pauses immediately (no meaningful "last
        # OK" to grant a grace window against, and monotonic() is not a
        # wall-clock we can compare to an absolute).
        never_confirmed = self._broker_ok_at == 0.0
        stale_for = now - self._broker_ok_at
        if never_confirmed or stale_for > BROKER_STALE_SEC:
            if not self._broker_degraded:
                LOG.warning(
                    "Broker health probe failing (%s); %s -- pausing entries",
                    detail,
                    "never confirmed since start" if never_confirmed
                    else f"last OK {stale_for:.0f}s ago (> {BROKER_STALE_SEC:.0f}s)",
                )
            self._broker_degraded = True
            out = {"enabled": True, "degraded": True, "detail": detail}
            if not never_confirmed:
                out["stale_for_sec"] = round(stale_for, 1)
            return out

        LOG.info(
            "Broker health probe failed (%s) but last OK only %.0fs ago "
            "(< %.0fs) -- not pausing yet",
            detail, stale_for, BROKER_STALE_SEC,
        )
        return {
            "enabled": True, "degraded": False, "detail": detail,
            "stale_for_sec": round(stale_for, 1), "within_grace": True,
        }

    # ------------------------------------------------------------------
    # Reconciliation — Phase 3's book is never left reflecting an assumed state
    # ------------------------------------------------------------------

    async def _reconcile_book_with_broker(self, prices: dict[str, float]) -> dict[str, Any]:
        # The broker fetch is network I/O -- do it OUTSIDE the book lock so a
        # slow broker can't stall the other process's cycle.
        actual = await self._fetch_broker_positions()
        now = time.monotonic()
        corrections: list[dict[str, Any]] = []
        deferred: list[str] = []
        # Cross-process lock: another orchestrator (the HTTP-route throwaway, or
        # the background worker) must not be mid read-decide-write on the book
        # while we correct it. Re-read the book INSIDE the lock -- it may have
        # changed since our broker fetch above.
        with book_lock(self._book_lock_path):
            open_positions = list_open_positions(self._book)
            expected = {p.symbol: (p.qty if p.side == "long" else -p.qty) for p in open_positions}
            portfolio_value = sum(abs(q) * prices.get(sym, 0.0) for sym, q in expected.items()) or 1.0
            report = self._reconciler.reconcile(expected, actual, portfolio_value)
            if report.drift_detected:
                LOG.warning(
                    "Book/broker drift detected: %d symbol(s), %.2f%% total",
                    len(report.symbol_drifts), report.total_drift_pct,
                )
                # how-to-make-it-live.md #15: don't just warn -- pull the book
                # back to broker truth. The broker is ground truth for what the
                # account actually holds (a partial fill, or a bracket leg that
                # fired between cycles). Skipped entirely when the broker
                # snapshot is empty (can't tell a real flat account from a
                # failed fetch).
                if RECONCILE_AUTOCORRECT and actual:
                    by_symbol = {p.symbol: p for p in open_positions}
                    for d in report.symbol_drifts:
                        sym = d["symbol"]
                        last = self._recently_traded.get(sym)
                        if (
                            RECONCILE_SETTLE_SEC > 0
                            and last is not None
                            and (now - last) < RECONCILE_SETTLE_SEC
                        ):
                            # fill hasn't propagated to /positions yet -- the
                            # next cycle reconciles it for real.
                            LOG.info(
                                "RECONCILE: deferring %s -- this instance traded it %.1fs ago "
                                "(< %.0fs settle)", sym, now - last, RECONCILE_SETTLE_SEC,
                            )
                            deferred.append(sym)
                            continue
                        corr = self._reconcile_symbol(
                            sym, by_symbol.get(sym),
                            actual.get(sym, 0.0), prices.get(sym, 0.0),
                        )
                        if corr:
                            corrections.append(corr)
        return {
            "drift_detected": report.drift_detected,
            "n_drifts": len(report.symbol_drifts),
            "total_drift_pct": report.total_drift_pct,
            "corrections": corrections,
            "deferred": deferred,
        }

    def _reconcile_symbol(
        self, symbol: str, book_pos: Position | None, broker_signed: float, price: float,
    ) -> dict[str, Any] | None:
        """Pull one symbol's book state toward the broker's real position.
        Returns a record of what was changed, or None if nothing safe to do."""
        book_signed = 0.0
        if book_pos is not None:
            book_signed = book_pos.qty if book_pos.side == "long" else -book_pos.qty

        # Phantom: broker holds something the book has no position for. Could
        # be another strategy, a manual trade, or a real bug -- never
        # auto-open, just alert.
        if book_pos is None:
            LOG.error(
                "RECONCILE: broker holds %.4f %s but the book has no position -- "
                "NOT auto-correcting (needs review)", broker_signed, symbol,
            )
            return {"symbol": symbol, "action": "alert_phantom_broker_position", "broker_qty": broker_signed}

        # Direction conflict: book long vs broker short (or vice versa). Serious
        # -- never auto-flip.
        if book_signed * broker_signed < 0:
            LOG.error(
                "RECONCILE: %s book is %s %.4f but broker is the opposite side %.4f -- "
                "NOT auto-correcting (needs review)", symbol, book_pos.side, book_pos.qty, broker_signed,
            )
            return {"symbol": symbol, "action": "alert_side_conflict", "book_qty": book_signed, "broker_qty": broker_signed}

        book_abs, broker_abs = abs(book_signed), abs(broker_signed)

        if broker_abs <= 1e-9:  # broker flat -> close the book position
            close_position(self._book, book_pos.position_id, price or book_pos.avg_entry)
            LOG.warning("RECONCILE: broker flat on %s -- closed stale book position (%.4f)", symbol, book_abs)
            return {"symbol": symbol, "action": "closed_to_match_broker", "was_qty": book_abs}

        if broker_abs < book_abs:  # book over-counts (partial entry / over-exit)
            reduce_position(self._book, book_pos.position_id, book_abs - broker_abs, price or book_pos.avg_entry)
            LOG.warning(
                "RECONCILE: %s book %.4f > broker %.4f -- reduced book to broker",
                symbol, book_abs, broker_abs,
            )
            return {"symbol": symbol, "action": "reduced_to_match_broker", "from_qty": book_abs, "to_qty": broker_abs}

        # broker_abs > book_abs: book under-counts (partial exit left residual
        # exposure, or an add we didn't record). Correct up so risk sees the
        # real size -- but refuse an absurd gap (that is a bug, not a fill).
        if broker_abs > book_abs * RECONCILE_MAX_RATIO:
            LOG.error(
                "RECONCILE: %s broker %.4f is >%.0fx the book %.4f -- NOT auto-correcting (needs review)",
                symbol, broker_abs, RECONCILE_MAX_RATIO, book_abs,
            )
            return {"symbol": symbol, "action": "alert_implausible_gap", "book_qty": book_abs, "broker_qty": broker_abs}
        add_to_position(self._book, book_pos.position_id, broker_abs - book_abs, price or book_pos.avg_entry)
        LOG.warning(
            "RECONCILE: %s book %.4f < broker %.4f -- added to book to match broker",
            symbol, book_abs, broker_abs,
        )
        return {"symbol": symbol, "action": "increased_to_match_broker", "from_qty": book_abs, "to_qty": broker_abs}

    async def _fetch_broker_positions(self) -> dict[str, float]:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return {
                        p.get("symbol", ""): float(p.get("qty", 0))
                        for p in data if p.get("symbol")
                    }
        except Exception as e:
            LOG.warning("Could not fetch broker positions: %s", e)
        return {}

    async def _entry_slippage_bps(
        self, symbol: str, planned_price: float, direction: str, pre_signed: float,
    ) -> float | None:
        """Stage A (A13 -- StockSharp's realized-slippage tracker, see
        other-repos-world/comprison-other-vinu/10-stocksharp.md): observed
        fill quality for a fresh entry. Positive bps = filled worse than the
        mark the order was sized against. Best-effort, monitoring-only --
        returns None (and never raises) on anything unexpected. Only
        meaningful when entering from flat, since the broker's blended
        avg-entry-price for an add is not this fill's price."""
        if abs(pre_signed) > 1e-9 or planned_price <= 0:
            return None
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
            if resp.status_code != 200:
                return None
            for p in resp.json() or []:
                if p.get("symbol") != symbol:
                    continue
                avg = float(p.get("avg_entry_price") or p.get("avg_entry") or 0.0)
                if avg <= 0:
                    return None
                raw_bps = (avg - planned_price) / planned_price * 10_000.0
                # For a short, filling *higher* than planned is favourable,
                # so flip the sign to keep "positive = worse" consistent.
                return raw_bps if direction == "long" else -raw_bps
        except Exception:
            return None
        return None

    async def _confirm_fill(
        self, symbol: str, pre_signed: float, intended_delta: float,
    ) -> tuple[float, bool]:
        """how-to-make-it-live.md #15: after a submit, poll the broker's real
        position and return (actual signed delta, was_partial).

        `pre_signed` is the broker's signed qty for `symbol` before this order
        (+ long / - short); `intended_delta` is the signed change the order was
        meant to produce. Falls back to (intended_delta, False) whenever the
        broker view is unavailable or shows nothing yet (async fill lag) --
        this never blocks or shrinks a position on a bad read; end-of-cycle
        reconciliation is the backstop for anything it misses.
        """
        if intended_delta == 0.0 or FILL_CONFIRM_ATTEMPTS <= 0:
            return intended_delta, False
        want = abs(intended_delta)
        for attempt in range(FILL_CONFIRM_ATTEMPTS):
            positions = await self._fetch_broker_positions()
            if not positions:
                return intended_delta, False  # untrusted snapshot -> fail open
            got = abs(positions.get(symbol, 0.0) - pre_signed)
            if got >= want * (1.0 - PARTIAL_FILL_TOLERANCE):
                return intended_delta, False  # full fill (within tolerance)
            if attempt < FILL_CONFIRM_ATTEMPTS - 1:
                await asyncio.sleep(FILL_CONFIRM_DELAY_SEC)
                continue
            if got <= 1e-9:
                return intended_delta, False  # nothing visible -> async lag
            signed = got if intended_delta > 0 else -got
            return signed, True  # genuine partial fill
        return intended_delta, False


def _simple_returns(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        return []
    return [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] != 0
    ]
