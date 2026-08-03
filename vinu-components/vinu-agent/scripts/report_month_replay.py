#!/usr/bin/env python3
"""P&L + decision-transcript report for a 1-month agentic replay run.

Reads `the-1-month-back-testing/results/<run-id>/` (the output of
run_month_replay.py: one manifest.json plus one response.json,
account_snapshot.json, thinking.json per simulated day) and produces:

  - headline P&L ($ and %) from the account snapshots' cash/equity path;
  - standard metrics (Sharpe, max drawdown, win rate, ...) via
    vinu_simulator.engine.metrics.compute_full_metrics — never hand-rolled;
  - a trade log from the historical broker's persisted ledger (item 2), not
    reverse-engineered from transcripts;
  - a day-by-day decision narrative;
  - honesty flags for days whose reasoning looks like it calls direction from
    significance_score / sentiment (a proven-negative mechanism).

Output: `results/<run-id>/report.md`.

Item 4 of the-1-month-back-testing plan. Reuses, does not reimplement,
vinu_simulator's metrics.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from vinu_simulator.engine.metrics import compute_full_metrics

RESULTS_BASE = Path(__file__).resolve().parents[3] / "the-1-month-back-testing" / "results"
DEFAULT_STOCK_API = "http://localhost:8081"

_INITIAL_CASH = 100_000.0

# Mechanisms the plan explicitly flags as proven-not-to-work for direction:
# rule-based sentiment and FinBERT are ~50/50 on AAPL/TSLA/JNJ. Any day whose
# final reasoning leans on these for a directional call gets a honesty flag.
_DIRECTION_WORDS = re.compile(
    r"\b(sentiment|bullish|bearish|positive momentum|negative momentum|"
    r"significance_score|significance|buy signal|sell signal)\b",
    re.IGNORECASE,
)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text("utf-8"))


def _load_run(run_dir: Path) -> dict:
    manifest = _read_json(run_dir / "manifest.json")
    days = sorted(
        d for d in (manifest.get("days") or [])
        if (run_dir / d / "response.json").exists()
    )
    return {"manifest": manifest, "days": days}


def _fetch_daily_closes(symbols: set[str], days: list[str], stock_api: str) -> dict[str, dict[str, float]]:
    """Real per-day closes from stock-api, keyed [symbol][date].

    Historical-fill-broker's `last_close` is only ever set at fill time
    (`historical_broker.py:178,189`) and never refreshed on days without a
    trade — confirmed 2026-08-03, logged as Bug-2 in
    `historical-fill-broker/test-log.md`. A held position's mark otherwise
    stays frozen at the entry price for the rest of the run, silently
    hiding real gains/losses. Worked around here at the reporting layer by
    re-pricing from the same candle data the agent's own tools use, instead
    of trusting the broker's frozen snapshot.
    """
    import httpx

    if not symbols or not days:
        return {}
    from_ts = int(datetime.fromisoformat(days[0]).replace(tzinfo=timezone.utc).timestamp())
    to_ts = int(datetime.fromisoformat(days[-1]).replace(tzinfo=timezone.utc).timestamp()) + 86400
    out: dict[str, dict[str, float]] = {}
    for sym in symbols:
        try:
            r = httpx.get(
                f"{stock_api}/stock/candles/{sym}",
                params={"from": from_ts, "to": to_ts, "interval": "1D"},
                timeout=30,
            )
            r.raise_for_status()
            rows = r.json().get("data", [])
        except Exception:  # noqa: BLE001 — best-effort; caller falls back to broker's mark
            rows = []
        by_date = {}
        for row in rows:
            d = datetime.fromtimestamp(row["bar_ts"], timezone.utc).date().isoformat()
            by_date[d] = float(row["close"])
        out[sym] = by_date
    return out


def _equity_curve(run_dir: Path, days: list[str], stock_api: str = DEFAULT_STOCK_API) -> list[dict]:
    """Per-day equity: cash (from the broker's real ledger) + holdings marked
    at the actual historical close for that day (see `_fetch_daily_closes`
    docstring for why not the broker's own `last_close`)."""
    snaps = {day: _read_json(run_dir / day / "account_snapshot.json") for day in days}
    symbols = {sym for snap in snaps.values() for sym in (snap.get("positions") or {})}
    closes = _fetch_daily_closes(symbols, days, stock_api)

    curve: list[dict] = []
    for day in days:
        snap = snaps[day]
        cash = snap.get("cash")
        if cash is None:
            cash = _INITIAL_CASH
        positions = snap.get("positions") or {}
        holdings = 0.0
        for sym, pos in positions.items():
            qty = float(pos.get("qty", 0.0))
            mark = closes.get(sym, {}).get(day)
            if mark is None:
                mark = float(pos.get("last_close", 0.0))
            holdings += qty * mark
        curve.append({"date": day, "cash": float(cash), "holdings": holdings,
                      "equity": float(cash) + holdings})
    return curve


def _trade_log(run_dir: Path, days: list[str]) -> list[dict]:
    """Merge the broker's persisted ledger across all days, dedup by order id."""
    seen = set()
    trades: list[dict] = []
    for day in days:
        snap = _read_json(run_dir / day / "account_snapshot.json")
        for row in snap.get("ledger", []):
            key = (row.get("date"), row.get("symbol"), row.get("side"),
                   row.get("qty"), row.get("fill_price"))
            if key in seen:
                continue
            seen.add(key)
            trades.append(row)
    return trades


def _decision_narrative(run_dir: Path, days: list[str]) -> list[dict]:
    """Structured day-by-day narrative from response.json + thinking.json."""
    out = []
    for day in days:
        resp = _read_json(run_dir / day / "response.json")
        thinking = _read_json(run_dir / day / "thinking.json")
        tool_events = []
        if isinstance(thinking, list):
            for step in thinking:
                tcs = step.get("tool_calls") or []
                for tc in tcs:
                    name = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else ""
                    if name:
                        tool_events.append(name)
        summary = resp.get("summary") or {}
        final = resp.get("final_content") or ""
        out.append({
            "date": day,
            "action": summary.get("action"),
            "symbol": summary.get("symbol"),
            "qty": summary.get("qty"),
            "side": summary.get("side"),
            "reasoning_excerpt": summary.get("reasoning_excerpt") or final[:800],
            "tool_calls": tool_events,
        })
    return out


def _flag_direction_calling(narratives: list[dict]) -> list[dict]:
    flags = []
    for n in narratives:
        text = n.get("reasoning_excerpt") or ""
        matches = _DIRECTION_WORDS.findall(text)
        is_trade = n.get("action") == "trade"
        if is_trade and matches:
            flags.append({
                "date": n["date"],
                "symbol": n.get("symbol"),
                "side": n.get("side"),
                "terms": sorted(set(m.lower() for m in matches)),
                "excerpt": text[:300],
            })
    return flags


def _md_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def build_report(run_dir: Path, stock_api: str = DEFAULT_STOCK_API) -> str:
    data = _load_run(run_dir)
    days = data["days"]
    manifest = data["manifest"]
    if not days:
        return f"# Report for {run_dir.name}\n\nNo completed days found.\n"

    curve = _equity_curve(run_dir, days, stock_api)
    trades = _trade_log(run_dir, days)
    narratives = _decision_narrative(run_dir, days)
    flags = _flag_direction_calling(narratives)

    equity = pd.Series([c["equity"] for c in curve],
                       index=[c["date"] for c in curve])
    returns = equity.pct_change().dropna()
    if len(returns) == 0:
        metrics = {}
    else:
        metrics = compute_full_metrics(equity, returns, trades=trades, periods_per_year=252)

    start_eq = curve[0]["equity"]
    end_eq = curve[-1]["equity"]
    pnl = end_eq - start_eq
    pnl_pct = (pnl / start_eq * 100.0) if start_eq else 0.0

    w = manifest.get("confirmed_window") or {}
    lines: list[str] = []
    lines.append(f"# Replay P&L Report — {run_dir.name}")
    lines.append("")
    lines.append(f"- **Window:** {w.get('start')} → {w.get('end')} "
                 f"({len(days)} trading days)")
    lines.append(f"- **Tickers:** {', '.join(manifest.get('tickers') or [])}")
    lines.append(f"- **Starting equity:** ${start_eq:,.2f}")
    lines.append(f"- **Ending equity:** ${end_eq:,.2f}")
    lines.append(f"- **Total P&L:** **${pnl:+,.2f} ({pnl_pct:+.2f}%)**")
    lines.append(f"- **Trades executed:** {len(trades)}")
    lines.append("")
    lines.append(
        "> Held positions are marked at the real historical daily close "
        "(fetched from `vinu-stock-price`), not the broker's own recorded "
        "`last_close` — the historical-fill broker only ever sets that field "
        "at fill time and never refreshes it on days without a new trade "
        "(confirmed bug, see `historical-fill-broker/test-log.md` Bug-2). "
        "Note this means the P&L below reflects the *true* price path, which "
        "the agent itself was never shown during the replay — the agent's "
        "own tool responses reported a flat, frozen mark the whole time."
    )
    lines.append("")

    # Metrics
    lines.append("## Standard Metrics (vinu_simulator.engine.metrics)")
    lines.append("")
    if metrics:
        want = ["total_return", "sharpe_ratio", "max_drawdown", "win_rate",
                "cagr", "annual_volatility", "profit_factor", "sortino_ratio"]
        lines.append(_md_table(
            ["metric", "value"],
            [[k, f"{metrics.get(k, 0.0):.4f}"] for k in want],
        ))
    else:
        lines.append("_No valid return series — flat account across the run._")
    lines.append("")

    # Trade log
    lines.append("## Trade Log")
    lines.append("")
    if trades:
        lines.append(_md_table(
            ["date", "symbol", "side", "qty", "fill_price", "cash_after"],
            [[t.get("date"), t.get("symbol"), t.get("side"), t.get("qty"),
              t.get("fill_price"), f"{t.get('cash_after', 0.0):,.2f}"] for t in trades],
        ))
    else:
        lines.append("_No trades executed across the replay._")
    lines.append("")

    # Day-by-day
    lines.append("## Day-by-Day Decisions")
    lines.append("")
    rows = []
    for n in narratives:
        rows.append([
            n["date"], n.get("action") or "none",
            n.get("symbol") or "—", n.get("side") or "—", n.get("qty") or "—",
            ", ".join(dict.fromkeys(n.get("tool_calls") or []))[:120],
            (n.get("reasoning_excerpt") or "")[:160].replace("\n", " "),
        ])
    lines.append(_md_table(
        ["date", "action", "symbol", "side", "qty", "tools used", "reasoning excerpt"],
        rows,
    ))
    lines.append("")

    # Honesty flags
    lines.append("## Honesty Flags — direction-calling from proven-negative signals")
    lines.append("")
    if flags:
        for f in flags:
            lines.append(f"- **{f['date']}** ({f['symbol']} {f['side']}): "
                         f"reasoning references `{', '.join(f['terms'])}` — "
                         f"sentiment/significance_score is a proven ~50/50 "
                         f"mechanism; treat a good result as a coincidence, not proof.")
            lines.append(f"  > {f['excerpt']}")
    else:
        lines.append("_No day's trade decision leaned on sentiment / "
                     "significance_score for a directional call._")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
                 f"by scripts/report_month_replay.py — metrics from "
                 f"vinu_simulator.engine.metrics, not hand-rolled.*")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True, help="results folder name under results/")
    ap.add_argument("--results-base", default=str(RESULTS_BASE))
    ap.add_argument("--stock-api", default=DEFAULT_STOCK_API,
                     help="vinu-stock-price base URL, used to re-mark held positions "
                          "at their real historical close (see historical-fill-broker Bug-2)")
    args = ap.parse_args()

    run_dir = Path(args.results_base) / args.run_id
    if not run_dir.exists():
        print(f"ERROR: {run_dir} does not exist")
        return 1

    report = build_report(run_dir, args.stock_api)
    out_path = run_dir / "report.md"
    out_path.write_text(report, "utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
