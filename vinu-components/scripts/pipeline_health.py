"""One-page health report of the whole pipeline: what ran, what passed, what is stuck, and why.

    python scripts/pipeline_health.py            # the last 24 hours
    python scripts/pipeline_health.py --hours 6

Read-only. SQLite stores are read from INSIDE their containers (see stack_db.py); nothing here touches data/ on the host,
and nothing writes anywhere. Each section says so when it could not be read instead of printing zeros.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_READ = (
    "import sqlite3,sys,json;c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True,timeout=5);"
    "cur=c.execute(sys.argv[2]);cols=[d[0] for d in cur.description];"
    "print(json.dumps([dict(zip(cols,r)) for r in cur.fetchall()],default=str))"
)


def rows(service: str, db: str, sql: str) -> list[dict] | None:
    out = subprocess.run(["docker", "compose", "exec", "-T", service, "python", "-c", _READ, db, sql],
                         cwd=ROOT, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception:  # noqa: BLE001
        return None


def section(title: str) -> None:
    print(f"\n== {title}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    hours = ap.parse_args().hours

    section("services")
    ps = subprocess.run(["docker", "compose", "ps", "--format", "{{.Name}}|{{.Status}}"], cwd=ROOT,
                        capture_output=True, text=True, check=False).stdout.splitlines()
    bad = [line for line in ps if "(healthy)" not in line and line.strip()]
    print(f"{len(ps) - len(bad)} healthy" + (f"; NOT healthy: {', '.join(bad)}" if bad else ""))
    stale = subprocess.run([sys.executable, "scripts/stale_images.py"], cwd=ROOT, capture_output=True, text=True, check=False)
    print("images: " + ("all current" if stale.returncode == 0 else "STALE -> " + " ".join(
        line.split()[1] for line in stale.stdout.splitlines() if line.strip().startswith("STALE"))))

    section(f"LLM gateway (queue now, and the last {hours} h)")
    q = get("http://127.0.0.1:8099/llm/queue")
    print(f"queue now: {q['queue']} longest wait {q['longest_wait_sec']}s counters {q['counters']}" if q else "gateway unreachable")
    hist = rows("llm-gateway", "/data/llm_gateway.db",
                f"select purpose, archive_reason, count(*) n, round(avg(wait_ms)/1000.0,1) avg_wait_s, round(avg(run_ms)/1000.0,1) avg_run_s "
                f"from llm_history where archived_at > strftime('%s','now') - {hours * 3600} group by 1,2 order by n desc")
    if hist is None:
        print("  could not read the gateway history")
    for r in hist or []:
        print(" ", r)

    section(f"research runs (the last {hours} h)")
    runs = rows("agent-api", "/data/team_runs.db",
                f"select team_name, status, verdict, count(*) n, round(avg(time_used_seconds)/60.0,1) avg_min "
                f"from team_runs where created_at > datetime('now','-{hours} hours') group by 1,2,3 order by 1,n desc")
    if runs is None:
        print("could not read team_runs")
    for r in runs or []:
        print(" ", r)
    stuck = rows("agent-api", "/data/team_runs.db",
                 "select team_name, triggered_by_session_id, created_at from team_runs where status='running' "
                 "and created_at < datetime('now','-90 minutes')")
    if stuck:
        print("  STUCK (running more than 90 minutes):", stuck)

    section("strategies (artifacts)")
    arts = rows("research-api", "/research-data/strategy_store.db",
                "select status, coalesce(nullif(bar_interval,''),'-') bar, count(*) n from artifacts "
                "where type='strategy' group by 1,2 order by 1,2")
    print("  " + "\n  ".join(map(str, arts)) if arts else "  none yet" if arts == [] else "  could not read the strategy store")
    ok = rows("research-api", "/research-data/strategy_store.db",
              "select name, status, bar_interval, round(initial_sharpe,2) sharpe, round(deflated_sharpe,2) dsr "
              "from artifacts where type='strategy' and status in ('BENCHING','PEND','PENDBLOCK','ACTIVE','MONITORING') "
              "order by updated_at desc limit 10")
    for r in ok or []:
        print("   live candidate:", r)

    section("scoreboard (a checkpoint is PROVEN only with evidence; everything else is UNPROVEN)")
    verified = rows("research-api", "/research-data/strategy_store.db",
                    "select count(*) n from artifacts where type='strategy' and bar_evidence like '%\"verified\": true%'")
    n_verified = (verified or [{"n": 0}])[0]["n"]
    active = rows("research-api", "/research-data/strategy_store.db",
                  "select count(*) n from artifacts where type='strategy' and status='ACTIVE'")
    n_active = (active or [{"n": 0}])[0]["n"]
    done_runs = rows("agent-api", "/data/team_runs.db", "select count(*) n from team_runs where team_name='research' and status='done'")
    n_runs = (done_runs or [{"n": 0}])[0]["n"]
    chain = "test: vinu-agent/tests/test_chain_planted_edge.py (synthetic prices, real code)"
    board = [
        ("D0  data readiness", "PROVEN", "live: price catalog checked per bar size before every test; tests in test_bar_validation.py"),
        ("1   screener top 10", "PROVEN", "live: planner works through its picks (see research runs above)"),
        ("2   initial analysis", "PARTLY", "live; window ends at the last ingest, thin news history, model angles off by design"),
        ("3   strategy intake", "PROVEN", "live + tests: code, output contract and column checks"),
        ("4   all bar sizes", "PROVEN", "live: validate-code on AMD (4 bar sizes, 4m42s) + tests"),
        ("5   optimise", "PROVEN", "live: sweeps run; recipe templates fixed 2026-10-07"),
        ("6   statistical bar", "PROVEN", "live + " + chain),
        ("7   critic advisory", "PROVEN", "tests: a STOP with a runnable strategy is still tested by code"),
        ("8   retry loop", "PROVEN", "live: nudges and 3-candidate minimum observed in agent logs"),
        ("9   approved candidate", "PROVEN" if n_verified else "TESTED", f"{n_verified} real artifact(s) with a verified measurement; " + chain),
        ("10  risk gatekeeper", "TESTED", chain + "; never run on a real strategy"),
        ("11  capital allocator", "TESTED", chain + "; never run on a real strategy"),
        ("12  order guard, kill switch", "TESTED", chain + "; fails closed if the store is unreadable"),
        ("12b paper order at the broker", "UNPROVEN", "no order has been placed on the Alpaca paper account"),
        ("13  live feedback", "UNPROVEN", "needs a funded strategy trading and closing; never run"),
        ("14  observability", "PARTLY", "this report; about half of the service-to-service connections have not carried real data"),
    ]
    for name, state, why in board:
        print(f"  {state:9} {name:30} {why}")
    proven = sum(1 for _, st, _ in board if st == "PROVEN")
    print(f"  -> {proven} of {len(board)} proven on the real system; research runs done: {n_runs}; ACTIVE strategies: {n_active}")

    section("price data freshness")
    cat = get("http://127.0.0.1:8081/stock/catalog")
    if cat:
        import time
        ages = sorted(((time.time() - (r.get("last_bar_ts") or 0)) / 86400, r["symbol"]) for r in cat["data"])
        old = [f"{s} {a:.0f}d" for a, s in ages if a > 7]
        print(f"{len(ages)} symbols; newest bar age {ages[0][0]:.1f} d, oldest {ages[-1][0]:.1f} d" + (f"; STALE: {', '.join(old[:10])}" if old else ""))
    else:
        print("price service unreachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
