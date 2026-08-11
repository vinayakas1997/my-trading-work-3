from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$([\d,]+(?:\.\d+)?)")
_TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")
_PCT_RE = re.compile(r"([+-]?[\d]+(?:\.[\d]+)?)%")
_SHARES_RE = re.compile(r"([\d,]+)\s*shares?", re.IGNORECASE)

_KNOWN_TICKERS = frozenset({
    "AAPL", "TSLA", "JNJ", "MSFT", "AMZN", "GOOG", "META", "NVDA",
    "AMD", "INTC", "SPY", "QQQ", "IWM", "VXX", "GLD", "SLV",
})

_PRICE_TOLERANCE = 0.015


def _is_likely_ticker(word: str) -> bool:
    w = word.upper()
    if w in _KNOWN_TICKERS:
        return True
    if len(w) < 2 or len(w) > 5:
        return False
    if not w.isalpha():
        return False
    return True


def _associate_number_with_symbol(
    content: str, match_start: int, match_end: int
) -> str | None:
    """Return the nearest ticker symbol within ~120 chars of a numeric match."""
    window = content[max(0, match_start - 120):match_end + 120]
    before = content[max(0, match_start - 120):match_start]
    after = content[match_end:match_end + 120]

    candidates_before = _TICKER_RE.findall(before)
    candidates_after = _TICKER_RE.findall(after)

    candidates: list[str] = []
    for c in candidates_before:
        if _is_likely_ticker(c):
            candidates.append(c.upper())
    for c in candidates_after:
        if _is_likely_ticker(c) and c.upper() not in candidates:
            candidates.append(c.upper())

    if not candidates:
        return None
    return candidates[0] if before else candidates[0]


def _parse_price(raw: str) -> float:
    return float(raw.replace(",", ""))


def _numbers_in_text(text: str) -> list[float]:
    """Same three claim-shapes _extract_claims looks for in a final answer,
    applied to a tool result's own text -- needed because a manager's only
    "tool result" for a delegated task is delegate_to_agent's JSON, whose
    real numbers live inside the specialist's prose `content` string, not
    as JSON numeric literals. Without this, every number a specialist
    correctly computed and reported reads as ungrounded once the manager
    repeats it, a false Fail rather than a real hallucination."""
    values: list[float] = []
    for m in _PRICE_RE.finditer(text):
        values.append(_parse_price(m.group(1)))
    for m in _PCT_RE.finditer(text):
        values.append(float(m.group(1)))
    for m in _SHARES_RE.finditer(text):
        values.append(float(m.group(1).replace(",", "")))
    return values


def _values_near(target: float, candidates: list[float]) -> bool:
    for c in candidates:
        if abs(c - target) <= max(abs(target * _PRICE_TOLERANCE), 0.50):
            return True
    return False


class FactAuditor:
    """Post-hoc audit: extract numeric claims from the final answer and verify
    each against this turn's actual tool results.

    Three verdicts:
    - Verified — matching value found in this turn's tool results
    - Stale    — matching value found only in historical context (previous
                 turns/days), not from a fresh tool call this turn
    - Fail     — no matching value in any tool result, anywhere"""

    def audit(self, final_content: str, history: list[dict], session_id: str = "") -> list[dict]:
        """Return a list of audit-finding dicts, one per claim."""
        claims = self._extract_claims(final_content)
        if not claims:
            return []

        tool_results_this_turn: list[dict] = []
        tool_results_historical: list[dict] = []
        for msg in history:
            if msg.get("role") != "tool":
                continue
            if msg.get("name") is not None or msg.get("tool_call_id") is not None:
                tool_results_this_turn.append(msg)
            else:
                tool_results_historical.append(msg)

        findings: list[dict] = []
        for claim in claims:
            verdict = self._verdict(
                claim, tool_results_this_turn, tool_results_historical,
            )
            findings.append({
                "symbol": claim["symbol"] or "",
                "claimed_value": claim["value"],
                "claim_type": claim["type"],
                "raw_match": claim["raw"],
                "verdict": verdict,
            })

        try:
            from ..broker.kill_switch import AuditLogger
            for f in findings:
                if f["verdict"] == "Fail":
                    AuditLogger.log(
                        AuditLogger.AUDIT_VERDICT_FAIL,
                        details={"claim_type": f["claim_type"], "value": f["claimed_value"], "raw": f["raw_match"]},
                        session_id=session_id,
                        symbol=f["symbol"],
                    )
                elif f["verdict"] == "Stale":
                    AuditLogger.log(
                        AuditLogger.AUDIT_VERDICT_STALE,
                        details={"claim_type": f["claim_type"], "value": f["claimed_value"], "raw": f["raw_match"]},
                        session_id=session_id,
                        symbol=f["symbol"],
                    )
        except Exception:
            pass

        for f in findings:
            if f["verdict"] in ("Stale", "Fail"):
                logger.warning(
                    "FACT-AUDIT %s: %s %s=%s (claim: %r)",
                    f["verdict"].upper(),
                    f["symbol"],
                    f["claim_type"],
                    f["claimed_value"],
                    f["raw_match"][:80],
                )

        return findings

    def _extract_claims(self, content: str) -> list[dict]:
        """Regex-extract symbol + numeric claims from the final answer."""
        claims: list[dict] = []
        seen: set[tuple[str, str, float]] = set()

        for m in _PRICE_RE.finditer(content):
            symbol = _associate_number_with_symbol(content, m.start(), m.end())
            value = _parse_price(m.group(1))
            key = (symbol or "", "price", value)
            if key not in seen:
                seen.add(key)
                claims.append({
                    "symbol": symbol,
                    "value": value,
                    "type": "price",
                    "raw": m.group(),
                })

        for m in _PCT_RE.finditer(content):
            symbol = _associate_number_with_symbol(content, m.start(), m.end())
            value = float(m.group(1))
            key = (symbol or "", "pct", value)
            if key not in seen:
                seen.add(key)
                claims.append({
                    "symbol": symbol,
                    "value": value,
                    "type": "pct",
                    "raw": m.group(),
                })

        for m in _SHARES_RE.finditer(content):
            symbol = _associate_number_with_symbol(content, m.start(), m.end())
            value = float(m.group(1).replace(",", ""))
            key = (symbol or "", "shares", value)
            if key not in seen:
                seen.add(key)
                claims.append({
                    "symbol": symbol,
                    "value": value,
                    "type": "shares",
                    "raw": m.group(),
                })

        return claims

    def _verdict(
        self,
        claim: dict,
        this_turn: list[dict],
        historical: list[dict],
    ) -> str:
        """Determine whether a claim's value appears in tool results."""
        target = claim["value"]
        is_price = claim["type"] == "price"

        for tool_msg in this_turn:
            if self._value_in_content(target, tool_msg.get("content", ""), is_price):
                return "Verified"

        for tool_msg in historical:
            if self._value_in_content(target, tool_msg.get("content", ""), is_price):
                return "Stale"

        return "Fail"

    @staticmethod
    def _value_in_content(target: float, content: str, is_price: bool) -> bool:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return False

        candidates = FactAuditor._collect_numerics(data)
        if is_price:
            return _values_near(target, candidates)
        return any(abs(c - target) < 1e-6 for c in candidates)

    @staticmethod
    def _collect_numerics(obj) -> list[float]:
        results: list[float] = []
        if isinstance(obj, bool):
            pass
        elif isinstance(obj, (int, float)):
            results.append(float(obj))
        elif isinstance(obj, str):
            results.extend(_numbers_in_text(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                results.extend(FactAuditor._collect_numerics(v))
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                results.extend(FactAuditor._collect_numerics(v))
        return results
