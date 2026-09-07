#!/usr/bin/env python3
"""Per-stage timing collector + predictor for VINU test runs.

Reads the pipeline's own stores (no service changes, no rebuild):
  - data/agent/team_runs.db      precise durations + LLM calls per team run
  - data/agent/ticker_ledger.db  stage event timestamps per ticker

Commands:
  collect  --run-id ID    append timing rows for a test run to
                          ../new-vision/test-plan/test-status/timings.jsonl
  baselines [--promote]   print p50/p90 per stage from timings.jsonl
                          (--promote writes timing-baselines.json)
  predict  --tickers A,B  print ETA breakdown for a planned run:
                          compute sum (baselines) + cadence waits
                          (worker intervals from .env). Use BEFORE a run.
  progress --run-id ID    compare landed stages vs baselines: ahead/behind
                          per stage + ETA remaining. Use DURING a run.

Stage model (test-plan names). team_runs maps: screener -> summary_agent,
research -> sweep_execute (verdict rides the same run). Ledger anchors the
rest; dwell between a stage's first event and the next stage's first event
is recorded as that stage's wall time (includes cadence waits by design --
see predict, which models waits explicitly instead).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent  # vinu-components/
TEST_STATUS = ROOT.parent / "new-vision" / "test-plan" / "test-status"
TIMINGS_FILE = TEST_STATUS / "timings.jsonl"
BASELINES_FILE = TEST_STATUS / "timing-baselines.json"

STAGES = [
    "watchlist_gate", "summary_agent", "planner_triage", "planner_idea",
    "sweep_execute", "sweep_verdict", "risk_gatekeeper", "capital_allocator",
    "live_shadow", "monitor",
]
TEAM_TO_STAGE = {"screener": "summary_agent", "research": "sweep_execute"}

# test-plan stage -> real TickerLedger.stage values (see ledger.md mapping note)
LEDGER_STAGE_MAP = {
    "watchlist_gate": {"runlog_trigger", "change_gate"},
    "summary_agent": {"summary_agent"},
    "planner_triage": {"planner"},
    "planner_idea": {"planner"},
    "sweep_execute": {"sweep", "research"},
    "sweep_verdict": {"sweep", "research"},
    "risk_gatekeeper": {"risk_gatekeeper"},
    "capital_allocator": {"capital_allocator"},
    "live_shadow": {"live_shadow", "shadow"},
    "monitor": {"monitor"},
}


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # team_runs uses "YYYY-MM-DDTHH:MM:SS", ledger "...+Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _connect(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        print(f"warn: missing {path}, skipping", file=sys.stderr)
        return None
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(name + "="):
                try:
                    return float(line.split("=", 1)[1].strip())
                except ValueError:
                    break
    return default


def cmd_collect(args) -> int:
    agent = ROOT / "data" / "agent"
    rows: list[dict] = []
    seen: set[tuple] = set()

    # 1) precise durations from team_runs
    con = _connect(agent / "team_runs.db")
    if con is not None:
        ledger_times = _summary_times()
        for r in con.execute(
            "SELECT run_id, team_name, status, verdict, llm_calls_used,"
            " time_used_seconds, created_at, completed_at FROM team_runs"
            " ORDER BY created_at"
        ):
            d = dict(r)
            team = (d["team_name"] or "").lower()
            stage = TEAM_TO_STAGE.get(team)
            if stage is None:
                continue
            start = _parse_ts(d["created_at"])
            end = _parse_ts(d["completed_at"]) or _now_dt()
            secs = d["time_used_seconds"]
            duration = float(secs) if secs else ((end - start).total_seconds() if start else 0.0)
            ticker = _ticker_for_run(d["run_id"])
            if not ticker:
                # screener runs aren't referenced by ledger ref_ids; fall back
                # to nearest summary_refreshed event in time (±5 min).
                ticker = _nearest_summary_ticker(ledger_times, d["created_at"])
            rows.append({
                "test_run_id": args.run_id, "ticker": ticker, "stage": stage,
                "started_at": d["created_at"], "ended_at": d["completed_at"],
                "duration_s": round(duration, 1),
                "llm_calls": d["llm_calls_used"] or 0,
                "verdict": d["verdict"] or "", "status": d["status"] or "",
                "evidence_ref": d["run_id"], "source": "team_runs",
                "collected_at": _now(),
            })
            seen.add((ticker, stage, d["run_id"]))
        con.close()

    # 2) ledger anchors: first event ts per (ticker, mapped stage)
    con = _connect(agent / "ticker_ledger.db")
    if con is not None:
        events: dict[tuple, list] = {}
        for r in con.execute(
            "SELECT ticker, stage, event_type, timestamp, ref_id, text"
            " FROM ticker_ledger ORDER BY timestamp"
        ):
            d = dict(r)
            for test_stage, real in LEDGER_STAGE_MAP.items():
                if d["stage"] in real:
                    events.setdefault((d["ticker"], test_stage), []).append(d)
        for (ticker, stage), evs in sorted(events.items()):
            first, last = evs[0], evs[-1]
            t0, t1 = _parse_ts(first["timestamp"]), _parse_ts(last["timestamp"])
            dwell = (t1 - t0).total_seconds() if t0 and t1 else 0.0
            rows.append({
                "test_run_id": args.run_id, "ticker": ticker, "stage": stage,
                "started_at": first["timestamp"], "ended_at": last["timestamp"],
                "duration_s": round(dwell, 1), "llm_calls": 0,
                "verdict": "", "status": f"{len(evs)} events",
                "evidence_ref": first["ref_id"] or "",
                "note": first["text"][:120] if len(evs) == 1 else f"{len(evs)} events",
                "source": "ledger",
                "collected_at": _now(),
            })
        con.close()

    TEST_STATUS.mkdir(parents=True, exist_ok=True)
    existing = set()
    if TIMINGS_FILE.exists():
        for line in TIMINGS_FILE.read_text().splitlines():
            try:
                o = json.loads(line)
                existing.add((o.get("test_run_id"), o.get("ticker"), o.get("stage"),
                              o.get("evidence_ref"), o.get("source")))
            except json.JSONDecodeError:
                pass
    added = 0
    with open(TIMINGS_FILE, "a", encoding="utf-8") as f:
        for row in rows:
            key = (row["test_run_id"], row["ticker"], row["stage"],
                   row["evidence_ref"], row["source"])
            if key in existing:
                continue
            f.write(json.dumps(row) + "\n")
            existing.add(key)
            added += 1
    print(f"collect: {added} new rows -> {TIMINGS_FILE} ({len(rows)} scanned)")
    return 0


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _ticker_for_run(run_id: str) -> str:
    """Best-effort ticker for a team run: TickerLedger rows carry the run_id
    as ref_id alongside the ticker (triage/summary events)."""
    try:
        agent = ROOT / "data" / "agent"
        led = sqlite3.connect(str(agent / "ticker_ledger.db"))
        row = led.execute(
            "SELECT ticker FROM ticker_ledger WHERE ref_id=? LIMIT 1", (run_id,)
        ).fetchone()
        led.close()
        if row and row[0]:
            return str(row[0]).upper()
    except sqlite3.Error:
        pass
    return ""


def _summary_times() -> list[tuple]:
    """(timestamp, ticker) of summary_refreshed ledger events for fallback
    attribution of screener runs (which carry no ledger ref)."""
    out: list[tuple] = []
    try:
        agent = ROOT / "data" / "agent"
        led = sqlite3.connect(str(agent / "ticker_ledger.db"))
        for t, ts in led.execute(
            "SELECT ticker, timestamp FROM ticker_ledger"
            " WHERE stage='summary_agent' ORDER BY timestamp"
        ):
            dt = _parse_ts(ts)
            if dt:
                out.append((dt, str(t).upper()))
        led.close()
    except sqlite3.Error:
        pass
    return out


def _nearest_summary_ticker(events: list[tuple], created_at: str | None) -> str:
    dt = _parse_ts(created_at)
    if not dt or not events:
        return ""
    best, best_gap = "", 300.0
    for ets, ticker in events:
        gap = abs((ets - dt).total_seconds())
        if gap < best_gap:
            best, best_gap = ticker, gap
    return best


def _load_timings() -> list[dict]:
    if not TIMINGS_FILE.exists():
        return []
    out = []
    for line in TIMINGS_FILE.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _percentile(xs: list[float], pct: float) -> float:
    if not xs:
        return 0.0
    return statistics.quantiles(sorted(xs), n=100, method="inclusive")[min(99, max(0, int(pct) - 1))]


def cmd_baselines(args) -> int:
    rows = [r for r in _load_timings() if r.get("source") == "team_runs"]
    by_stage: dict[str, dict] = {}
    for r in rows:
        b = by_stage.setdefault(r["stage"], {"durations": [], "calls": [], "n": 0})
        b["durations"].append(float(r.get("duration_s") or 0))
        b["calls"].append(int(r.get("llm_calls") or 0))
        b["n"] += 1
    baselines = {}
    print(f"{'stage':<18}{'n':>4}{'p50_s':>9}{'p90_s':>9}{'p50_calls':>10}")
    for stage in STAGES:
        b = by_stage.get(stage, {"durations": [], "calls": [], "n": 0})
        p50 = round(statistics.median(b["durations"]), 1) if b["durations"] else 0.0
        p90 = round(_percentile(b["durations"], 90), 1) if b["durations"] else 0.0
        c50 = int(statistics.median(b["calls"])) if b["calls"] else 0
        baselines[stage] = {"n": b["n"], "p50_s": p50, "p90_s": p90, "p50_calls": c50}
        print(f"{stage:<18}{b['n']:>4}{p50:>9.1f}{p90:>9.1f}{c50:>10d}")
    if args.promote:
        BASELINES_FILE.write_text(json.dumps(
            {"promoted_at": _now(), "stages": baselines}, indent=2))
        print(f"promoted -> {BASELINES_FILE}")
    return 0


def _load_baselines() -> dict:
    if BASELINES_FILE.exists():
        try:
            return json.loads(BASELINES_FILE.read_text())["stages"]
        except (json.JSONDecodeError, KeyError):
            pass
    # fallback: compute live from timings.jsonl without promoting
    rows = [r for r in _load_timings() if r.get("source") == "team_runs"]
    out: dict = {}
    for stage in STAGES:
        ds = [float(r.get("duration_s") or 0) for r in rows if r.get("stage") == stage]
        cs = [int(r.get("llm_calls") or 0) for r in rows if r.get("stage") == stage]
        out[stage] = {
            "n": len(ds),
            "p50_s": round(statistics.median(ds), 1) if ds else 0.0,
            "p90_s": round(_percentile(ds, 90), 1) if ds else 0.0,
            "p50_calls": int(statistics.median(cs)) if cs else 0,
        }
    return out


def cmd_predict(args) -> int:
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    stages = [s.strip() for s in args.stages.split(",") if s.strip()] or STAGES
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        print(f"unknown stages: {unknown} (known: {', '.join(STAGES)})", file=sys.stderr)
        return 2
    base = _load_baselines()
    planner = _env_float("VINU_AGENT_PLANNER_INTERVAL", 1800.0)
    allocator = _env_float("VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL", 900.0)
    # Wait model (documented assumption): worker-gated handoffs each cost on
    # average half a cadence (uniform arrival). Gate->triage->sweep rides the
    # planner; risk->allocator rides the allocator; shadow/monitor ride their
    # own loops (unknown here -> counted as 0, flagged).
    waits = {
        "watchlist_gate": 0.0, "summary_agent": planner / 2, "planner_triage": 0.0,
        "planner_idea": 0.0, "sweep_execute": planner / 2, "sweep_verdict": 0.0,
        "risk_gatekeeper": 0.0, "capital_allocator": allocator / 2,
        "live_shadow": 0.0, "monitor": 0.0,
    }
    print(f"tickers: {', '.join(tickers)}   planner_interval={planner:.0f}s allocator_interval={allocator:.0f}s")
    print(f"{'stage':<18}{'compute/ticker':>15}{'x tickers':>13}{'+ wait':>9}")
    compute_total = wait_total = 0.0
    calls_total = 0
    for stage in stages:
        b = base.get(stage, {"n": 0, "p50_s": 0.0, "p50_calls": 0})
        comp = b["p50_s"] * len(tickers)
        wait = waits.get(stage, 0.0) * len(tickers)
        calls_total += b["p50_calls"] * len(tickers)
        compute_total += comp
        wait_total += wait
        flag = "  (no baseline yet)" if not b["n"] else ""
        print(f"{stage:<18}{b['p50_s']:>10.0f}s x{len(tickers):<3}{comp:>8.0f}s{wait:>9.0f}s{flag}")
    total = compute_total + wait_total
    print(f"{'TOTAL ETA':<18}{'':>15}{compute_total:>13.0f}s{wait_total:>9.0f}s  = {total / 60:.0f} min (+~{calls_total} LLM calls)")
    print("assumption: waits = half worker cadence per gated handoff; shadow/monitor loops unmodeled (0).")
    return 0


def cmd_progress(args) -> int:
    base = _load_baselines()
    rows = [r for r in _load_timings() if r.get("test_run_id") == args.run_id]
    if not rows:
        print(f"no timing rows for run {args.run_id} (run collect first)", file=sys.stderr)
        return 2
    landed: dict[tuple, dict] = {}
    for r in rows:
        if r.get("source") != "team_runs":
            continue
        landed[(r.get("ticker"), r.get("stage"))] = r
    tickers = sorted({t for t, _ in landed})
    stages = [s for s in STAGES if any((t, s) in landed for t in tickers)]
    print(f"run {args.run_id} vs baselines (p50):")
    print(f"{'ticker':<8}{'stage':<18}{'actual':>9}{'p50':>9}{'delta':>9}{'calls':>7}")
    for t in tickers:
        for s in stages:
            r = landed.get((t, s))
            if r is None:
                print(f"{t:<8}{s:<18}{'-- pending --'}")
                continue
            b = base.get(s, {"p50_s": 0.0})
            actual, p50 = float(r.get("duration_s") or 0), float(b.get("p50_s") or 0)
            delta = actual - p50
            mark = "LATE" if p50 and delta > max(60.0, p50) else ("early" if delta < 0 else "ok")
            print(f"{t:<8}{s:<18}{actual:>8.0f}s{p50:>8.0f}s{delta:>+8.0f}s{r.get('llm_calls', 0):>7}  {mark}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="VINU test-run timing collector/predictor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("collect", help="append timing rows for a run")
    p.add_argument("--run-id", required=True)
    p.set_defaults(fn=cmd_collect)
    p = sub.add_parser("baselines", help="p50/p90 per stage")
    p.add_argument("--promote", action="store_true",
                   help="write timing-baselines.json")
    p.set_defaults(fn=cmd_baselines)
    p = sub.add_parser("predict", help="ETA for a planned run (run BEFORE)")
    p.add_argument("--tickers", required=True, help="e.g. AAPL,MSFT,NVDA")
    p.add_argument("--stages", default=",".join(STAGES),
                   help="comma list, default all 10")
    p.set_defaults(fn=cmd_predict)
    p = sub.add_parser("progress", help="actual-vs-baseline during a run")
    p.add_argument("--run-id", required=True)
    p.set_defaults(fn=cmd_progress)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
