#!/usr/bin/env python3
"""UI v1 read-only status (17 step1): 1 SELECT shows checkbox, click run_id shows curve.

No live buttons. Read-only. Usage:
  python3 scripts/ui-status.py --symbol AAPL --granularity 1D
  python3 scripts/ui-status.py --all
  python3 scripts/ui-status.py --run-id <run_id>
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "vinu-components/data/initial-analysis/vinu_initial_analysis_runs.db"


def checkbox(all_rows: bool = False, symbol: str = "AAPL", granularity: str = "1D"):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    # 1D has no trend_session_structure by design (spec.yaml 1min,5min,15min,1H,4H only) -> expect 27.
    if all_rows:
        cur.execute("SELECT symbol, granularity, COUNT(DISTINCT CASE WHEN granularity='1D' AND angle_name='trend_session_structure' THEN NULL ELSE angle_name END) FROM runs GROUP BY symbol, granularity ORDER BY symbol, granularity")
        for sym, gran, n in cur.fetchall():
            mark = "x" if (gran == "1D" and n >= 27) or (gran in ("1H", "4H", "1min", "5min", "15min") and n >= 28) or (gran in ("1W", "1M", "6M") and n >= 1) else " "
            print(f"[{mark}] {sym} {gran} {n}")
    else:
        if granularity == "1D":
            cur.execute("SELECT COUNT(DISTINCT angle_name) FROM runs WHERE symbol=? AND granularity=? AND angle_name!='trend_session_structure'", (symbol, granularity))
        else:
            cur.execute("SELECT COUNT(DISTINCT angle_name) FROM runs WHERE symbol=? AND granularity=?", (symbol, granularity))
        n = cur.fetchone()[0]
        print(f"{symbol} {granularity} {n}/27" if granularity == "1D" else f"{symbol} {granularity} {n}")
    con.close()


def halt_banner() -> bool:
    """HALT banner (17 step3): .vinu-live/HALT or data/live HALT file."""
    for p in [Path.home() / ".vinu-live" / "HALT", Path("vinu-components/data/live/HALT")]:
        if p.exists():
            print(f"HALT ACTIVE: {p} — entries blocked, exits allowed")
            return True
    return False


def drill(run_id: str):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("SELECT symbol, angle_name, granularity, status, row_count, stored_at FROM runs WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    if not row:
        print(f"run_id {run_id} not found")
        sys.exit(1)
    print(f"symbol={row[0]} angle={row[1]} gran={row[2]} status={row[3]} rows={row[4]} stored={row[5]}")
    con.close()


def export_csv(path: str = "ui-status.csv"):
    """CSV export (17 step3): checkbox table to file."""
    import csv as _csv

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("SELECT symbol, granularity, COUNT(DISTINCT CASE WHEN granularity='1D' AND angle_name='trend_session_structure' THEN NULL ELSE angle_name END) FROM runs GROUP BY symbol, granularity ORDER BY symbol, granularity")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["symbol", "granularity", "distinct_angles"])
        w.writerows(cur.fetchall())
    con.close()
    print(f"wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--symbol", default="AAPL")
    ap.add_argument("--granularity", default="1D")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--csv", default="")
    a = ap.parse_args()
    halted = halt_banner()
    if a.run_id:
        drill(a.run_id)
    elif a.csv:
        export_csv(a.csv)
    else:
        checkbox(a.all, a.symbol, a.granularity)
    if halted:
        sys.exit(2)
