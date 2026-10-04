"""Send a live-decision strategy through the same research and simulation gates every other strategy faces.

A live-decision strategy is a YAML file of trigger conditions (`must_conditions`). Until now nothing tested it: it went
straight into the live loop. Here its conditions become a research candidate (a `UserStrategy` that holds for N bars after
each setup), the research loop runs it on the strategy's own bar size for each ticker in its universe (one iteration, so
the rules are tested exactly as written, not "improved"), and the system's own promotion bar judges the result:
deflated Sharpe, out-of-sample holdout, stress windows and PBO (`promotion.meets_promotion_bar`).

The stored result is keyed by a fingerprint of the exact rules (vinu_infra.strategy_fingerprint), so an edited strategy
does not inherit an old approval. The live loop only evaluates strategies, and only tickers, that passed. Anything that
cannot be tested (a condition with no backtest equivalent, no conditions at all, an unknown bar size) is `unvalidatable`,
which is blocked exactly like a failure.

What this does not test: the stop and the RSI-style confirmation conditions (the setup is tested, not the risk dial).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend
from vinu_infra.strategy_fingerprint import fingerprint, hold_bars, to_interval

MIN_PASS_SHARE = 0.6      # share of the universe that must pass for the strategy to count as validated

_DIRECT = re.compile(r"^(sma|ema|rsi|adx)_(\d+)$")
_DIST = re.compile(r"^dist_from_(sma|ema)_(\d+)$")


# ------------------------------------------------------------------------------------------------ conditions -> code

def _column(key: str) -> tuple[str, str] | None:
    """(indicator column the backtester provides, python expression for the condition's left-hand side), or None."""
    m = _DIRECT.match(key)
    if m:
        return key, f'data["{key}"]'
    m = _DIST.match(key)
    if m:
        base = f"{m.group(1)}_{m.group(2)}"
        return base, f'((close - data["{base}"]) / data["{base}"])'
    return None


def _expression(lhs: str, op: str, value: Any) -> str | None:
    if op in ("gt", "gte", "lt", "lte"):
        symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
        return f"({lhs} {symbol} {float(value)!r})"
    if op == "eq":
        return f"({lhs} == {float(value)!r})"
    if op == "neq":
        return f"({lhs} != {float(value)!r})"
    if op == "between":
        lo, hi = value
        return f"(({lhs} >= {float(lo)!r}) & ({lhs} <= {float(hi)!r}))"
    if op == "in":
        return f"({lhs}.isin({[float(v) for v in value]!r}))"
    return None


def conditions_to_code(must_conditions: list[dict[str, Any]], hold: int) -> tuple[str | None, list[str], list[str]]:
    """(code, indicator columns to request, problems). code is None when any condition cannot be expressed: a strategy
    that cannot be tested is not partly tested, it is unvalidatable."""
    problems: list[str] = []
    lines: list[str] = []
    indicators: list[str] = []
    for c in must_conditions:
        key = str(c.get("key", ""))
        col = _column(key)
        if col is None:
            problems.append(f"condition key '{key}' has no backtest equivalent")
            continue
        try:
            expr = _expression(col[1], str(c.get("operator", "gt")), c.get("value"))
        except (TypeError, ValueError):
            expr = None
        if expr is None:
            problems.append(f"condition on '{key}' uses an operator or value that cannot be tested")
            continue
        if col[0] not in indicators:
            indicators.append(col[0])
        lines.append(f"        setup = setup & {expr}")
    if not must_conditions:
        problems.append("no must_conditions: there is nothing to test")
    if problems:
        return None, [], problems
    code = (
        "import pandas as pd\n"
        "from vinu_simulator.engine.strategies import BaseStrategy\n\n\n"
        "class UserStrategy(BaseStrategy):\n"
        f"    HOLD = {int(hold)}\n\n"
        "    def generate_weights(self, data):\n"
        '        close = data["close"]\n'
        "        setup = pd.Series(True, index=data.index)\n"
        + "\n".join(lines) + "\n"
        "        return setup.shift(1).rolling(self.HOLD, min_periods=1).max().fillna(0.0)\n"
    )
    return code, indicators, []


# ------------------------------------------------------------------------------------------------------- the store

class StrategyValidationStore(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS strategy_validations (
        strategy_id  TEXT PRIMARY KEY,
        fingerprint  TEXT NOT NULL,
        interval     TEXT,
        status       TEXT NOT NULL,
        detail_json  TEXT NOT NULL DEFAULT '{}',
        updated_at   TEXT NOT NULL
    );
    """
    SCHEMA_VERSION = 1

    def save(self, strategy_id: str, fp: str, interval: str | None, status: str, detail: dict[str, Any]) -> None:
        self.upsert("strategy_validations", {
            "strategy_id": strategy_id, "fingerprint": fp, "interval": interval, "status": status,
            "detail_json": json.dumps(detail, default=str), "updated_at": datetime.now(timezone.utc).isoformat(),
        }, ["strategy_id"])

    def list(self) -> list[dict[str, Any]]:
        rows = self._get_conn().execute("SELECT * FROM strategy_validations ORDER BY strategy_id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
            out.append(d)
        return out


# ----------------------------------------------------------------------------------------------------- the runner

def _eligible(record: Any, config: Any) -> tuple[bool, list[str]]:
    """The system's own promotion bar applied to a finished run, exactly as approval does it."""
    from vinu_research.models import Artifact
    from vinu_research.promotion import meets_promotion_bar

    a = Artifact.create(type_="strategy", name="validation_probe", universe=[record.symbol])
    a.initial_sharpe = record.best_sharpe
    a.deflated_sharpe = record.deflated_sharpe
    a.holdout_passed = record.holdout_passed
    a.stress_test_passed = record.stress_test_passed
    a.pbo = record.pbo
    verdict = meets_promotion_bar(a, config)
    return verdict.eligible, list(verdict.reasons)


async def validate_strategy(service: Any, definition: dict[str, Any], from_date: str, to_date: str) -> dict[str, Any]:
    """Validate one strategy definition ({name, schedule, universe, must_conditions, live_decision_max_hold_bars}) and
    store the verdict. Returns the stored record."""
    store: StrategyValidationStore = service.strategy_validation_store
    name = str(definition.get("name", ""))
    conditions = list(definition.get("must_conditions") or [])
    schedule = definition.get("schedule")
    interval = to_interval(schedule)
    hold = hold_bars(definition.get("live_decision_max_hold_bars"))
    fp = fingerprint(conditions, schedule, definition.get("live_decision_max_hold_bars"))
    tickers = [str(t).upper() for t in (definition.get("universe") or [])]

    def finish(status: str, detail: dict[str, Any]) -> dict[str, Any]:
        store.save(name, fp, interval, status, detail)
        return {"strategy_id": name, "status": status, "fingerprint": fp, "interval": interval, "detail": detail}

    if interval is None:
        return finish("unvalidatable", {"reasons": [f"schedule '{schedule}' is not a bar size the system can test"]})
    if not tickers:
        return finish("unvalidatable", {"reasons": ["the strategy has no tickers in its universe"]})
    code, indicators, problems = conditions_to_code(conditions, hold)
    if code is None:
        return finish("unvalidatable", {"reasons": problems})

    store.save(name, fp, interval, "running", {"tickers": tickers})
    per_ticker: dict[str, Any] = {}
    for ticker in tickers:
        try:
            run = await service.run_research(
                user_idea=f"validate live-decision strategy {name} ({interval}) on {ticker}", symbol=ticker,
                from_date=from_date, to_date=to_date, strategy_code=code, indicators=indicators,
                interval=interval, max_iterations=1, validation=True,
            )
            if not run.get("total_iterations"):
                # Research did not run it at all (skipped). That is "not tested", never "rejected".
                first_line = (run.get("report_md") or "").strip().splitlines()[0] if run.get("report_md") else "no report"
                per_ticker[ticker] = {"eligible": False, "tested": False, "outcome": "not_run",
                                      "reasons": [f"research did not run it: {first_line}"], "run_id": run.get("id")}
                continue
            record = await service._run_in_thread(service._storage.get_run, run["id"])
            eligible, reasons = _eligible(record, service.config) if record is not None else (False, ["run record missing"])
            if run.get("outcome_status") != "passed" and eligible:
                eligible, reasons = False, ["the research loop did not pass it"]
            per_ticker[ticker] = {
                "eligible": bool(eligible), "tested": True, "reasons": reasons, "outcome": run.get("outcome_status"),
                "sharpe": run.get("best_sharpe"), "deflated_sharpe": run.get("deflated_sharpe"),
                "holdout_passed": run.get("holdout_passed"), "stress_test_passed": run.get("stress_test_passed"),
                "diagnosis": run.get("diagnosis", ""), "run_id": run.get("id"),
            }
        except Exception as exc:  # noqa: BLE001 -- one ticker failing must not hide the others
            per_ticker[ticker] = {"eligible": False, "tested": False, "reasons": [f"{type(exc).__name__}: {exc}"], "outcome": "error"}
    passed = sorted(t for t, d in per_ticker.items() if d["eligible"])
    tested = [t for t, d in per_ticker.items() if d.get("tested")]
    share = len(passed) / len(tickers)
    if not tested:
        # nothing was actually tested (all skipped or errored): that is not a rejection, it is unknown. Still blocked.
        status = "not_tested"
    else:
        status = "validated" if share >= MIN_PASS_SHARE else "rejected"
    return finish(status, {"eligible_tickers": passed, "pass_share": share, "required_share": MIN_PASS_SHARE,
                           "per_ticker": per_ticker, "window": [from_date, to_date], "hold_bars": hold})
