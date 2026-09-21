"""Deterministic, traceable run_id generation.

Replaces a bare `uuid4().hex[:12]` (opaque, no information without a
RunLog lookup) with a self-describing id: reading the id alone tells you
the ticker, which angle, which timeframe, the analysis window, and which
attempt this was for that exact bucket -- no database lookup needed.

Format: ``{ticker}_{angle_code}_{tf_code}_{start}_{end}_{seq}_{rand5}``
e.g. ``AAPL_arima_1d_220101_260701_01_a1b2c``

- ``angle_code`` / ``tf_code``: short, stable, hand-assigned codes (see
  ANGLE_SHORTCODES / TIME_FORMAT_CODES below) -- append-only, a code is
  never reassigned once given, same discipline as the angle ids
  themselves (real folder names under vinu_initial_analysis/angles/,
  which are already stable in practice).
- ``start`` / ``end``: analysis_from/analysis_until as UTC YYMMDD, or
  ``000000`` when not given (some call sites allow open-ended windows).
- ``seq``: how many completed runs already exist for this exact
  (ticker, angle, timeframe) bucket, zero-padded to at least 2 digits --
  best-effort (a plain RunLog count, not a locked/atomic increment).
- ``rand5``: 5 hex characters (uuid4, truncated) -- a real, deliberate
  collision-safety net for the one genuinely concurrent path
  (`server/routes_v1.py`'s `trigger` route spawns a real
  `threading.Thread` per call, so two near-simultaneous triggers for the
  same ticker/angle/timeframe/window could otherwise compute the same
  `seq` from a stale read). Not needed for the scheduled tier2 path
  (a single sequential loop, never concurrent) but kept on every id for
  one consistent format rather than two.

Separator is ``_``, not ``-``: some real tickers contain a literal
hyphen in their own symbol (e.g. share-class tickers like ``BRK-B``),
which would silently misalign a hyphen-delimited id.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

# Append-only: a code, once assigned, is never reassigned or removed,
# even if the angle itself is later renamed -- any run_id ever generated
# with today's code must stay decodable. New angles get a new short code
# appended here, chosen to be unique among the existing values.
ANGLE_SHORTCODES: dict[str, str] = {
    "arima": "arima",
    "backtesting_44_metrics": "bktest",
    "chronos": "chronos",
    "dlinear": "dlinear",
    "drawdown_deep_dive": "ddive",
    "exponential_smoothing": "expsm",
    "garch": "garch",
    "itransformer": "itrans",
    "kalman_filters": "kalman",
    "kronos": "kronos",
    "lag_llama": "laglm",
    "lpatchtst": "lptst",
    "lstm": "lstm",
    "moirai": "moirai",
    "moment": "moment",
    "news_price_causality": "newscau",
    "patchtst": "patchtst",
    "peer_relative_strength": "peerrs",
    "pnl_attribution": "pnlattr",
    "regime_analysis": "regime",
    "shock_clustering": "shkclus",
    "shock_personality": "shkpers",
    "tft": "tft",
    "timer_timerxl": "timerxl",
    "timesfm": "timesfm",
    "tips_regime_aware_transformer": "tips",
    "trend_lifecycle": "trendlc",
    "trend_session_structure": "trendss",
}

# Deliberately distinct minute/month codes (1min vs 1M would both
# lowercase to "1m" otherwise) -- see angles.yaml's real time_formats
# lists, which mix both scales (e.g. backtesting_44_metrics/
# regime_analysis declare "1M"/"6M" alongside "1min").
TIME_FORMAT_CODES: dict[str, str] = {
    "1min": "1mi",
    "5min": "5mi",
    "15min": "15mi",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
    "1M": "1mo",
    "6M": "6mo",
}

_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def _sanitize(value: str, max_len: int) -> str:
    """Lowercase, strip anything that isn't alphanumeric (so a rogue
    separator character can never end up inside a field), truncate."""
    cleaned = _SANITIZE_RE.sub("", value.lower())
    return cleaned[:max_len] or "unk"


def angle_code(angle_name: str) -> str:
    """The stable short code for a real angle id, or a sanitized
    fallback for one not yet in ANGLE_SHORTCODES -- never raises, so a
    brand-new angle doesn't break run_id generation before its code is
    added here."""
    known = ANGLE_SHORTCODES.get(angle_name)
    if known is not None:
        return known
    return _sanitize(angle_name, 10)


def time_format_code(time_format: str) -> str:
    """The stable short code for a real time_format, or a sanitized
    fallback for one not yet in TIME_FORMAT_CODES."""
    known = TIME_FORMAT_CODES.get(time_format)
    if known is not None:
        return known
    return _sanitize(time_format, 6)


def _format_date(ts: int | None) -> str:
    if ts is None:
        return "000000"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%y%m%d")


def generate_run_id(
    ticker: str,
    angle_name: str,
    time_format: str,
    analysis_from: int | None,
    analysis_until: int | None,
    sequence: int,
) -> str:
    """Build one deterministic, traceable run_id.

    `sequence` is 1-indexed ("how many prior completed runs exist for
    this exact bucket, plus one for this one") -- callers get it from
    `RunLog.next_sequence()`. Zero-padded to at least 2 digits (grows
    past 99 without truncating, rather than wrapping/colliding).
    """
    ticker_part = _sanitize(ticker, 10).upper()
    start = _format_date(analysis_from)
    end = _format_date(analysis_until)
    seq_part = f"{max(sequence, 0):02d}"
    rand_part = uuid4().hex[:5]
    return "_".join([
        ticker_part,
        angle_code(angle_name),
        time_format_code(time_format),
        start,
        end,
        seq_part,
        rand_part,
    ])
