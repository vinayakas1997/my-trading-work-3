#!/usr/bin/env python3
"""Pipeline failure watchdog: early catch + failure localization.

Read-only by design: it NEVER retries, restarts, or mutates the pipeline.
It inspects stores/logs and records incidents to
../new-vision/test-plan/test-status/failures.jsonl, deduped by
(check, ticker, stage) so a persistent fault reports once, not every poll.

Checks:
  W1 infra STOP      team_runs verdict STOP with infra signature
                     (InfrastructureError, 401/403, unreachable, empty data)
  W2 zero-data       fresh summary with angles_with_data=0
  W3 empty market    watchlisted ticker with no recent daily candles
                     (via stock-api; needs VINU_API_KEY, 2 consecutive polls
                     to fire -- state kept in failures.jsonl history)
  W4 stage overrun   team run duration > 3x baseline p50 (or >15 min with no
                     baseline yet)
  W5 auth regression live 401/403 probe on internal endpoints -- runs the
                     same matrix as the ATS preflight (needs docker + key)
  W6 worker silence   no new TickerLedger row in >2x worker cadence
                     (planner 60min, allocator 30min defaults from .env)
  W7 resource press. container mem >85% of limit; non-running containers
                     (OOM/crash). Needs docker CLI; skipped without it.

Usage:
  watchdog.py --watch [--data DIR] [--failures PATH]
  watchdog.py --daemon --interval 300
Exit code: 0 clean (or only pre-existing acked), 1 open failures.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent  # vinu-components/
TEST_STATUS = ROOT.parent / "new-vision" / "test-plan" / "test-status"
FAILURES_FILE = TEST_STATUS / "failures.jsonl"
BASELINES_FILE = TEST_STATUS / "timing-baselines.json"

INFRA_KEYWORDS = (
    "infrastructureerror", "infrastructure failure", "401", "403",
    "unauthorized", "unreachable", "no weight data", "zero price data",
    "no price data", "empty", "data blocker",
    "simulator down", "circuit open",
)
ZERO = "2026-09-07T00:00:00Z"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(s: str | None):
    if not s:
        return None
    try:
        s = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_s(ts: str | None) -> float | None:
    dt = _parse_ts(ts)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "").strip()
    if v:
        return v
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return default


def _live_interval(service: str, name: str, default: float) -> float:
    """Running config wins over staged config: read the interval from the
    live container env first (a .env edit only takes effect after
    recreate), fall back to host/.env default."""
    import subprocess as _sp
    try:
        out = _sp.run(
            ["docker", "compose", "exec", "-T", service, "printenv", name],
            capture_output=True, text=True, timeout=20, cwd=str(ROOT),
        )
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except (OSError, ValueError, _sp.TimeoutExpired):
        pass
    try:
        return float(_env(name, "") or default)
    except ValueError:
        return default


def _connect(db: Path):
    if not db.exists():
        return None
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def _load_failures(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _latest_status(rows: list[dict]) -> dict[tuple, str]:
    """key -> latest status (append-only log: last row per key wins)."""
    latest: dict[tuple, str] = {}
    for f in rows:
        key = (f.get("check"), f.get("ticker"), f.get("stage"), f.get("evidence_ref"))
        latest[key] = f.get("status", "open")
    return latest


def _baselines() -> dict:
    try:
        return json.loads(BASELINES_FILE.read_text())["stages"]
    except (OSError, json.JSONDecodeError, KeyError):
        return {}


class Watch:
    def __init__(self, data_dir: Path, failures: Path):
        self.data = data_dir
        self.failures_path = failures
        self.prior = _load_failures(failures)
        latest = _latest_status(self.prior)
        self.open_keys = {k for k, v in latest.items() if v == "open"}
        self.new: list[dict] = []

    def resolve(self, check: str, ticker: str, stage: str, evidence_ref: str,
                note: str) -> None:
        """Close a previously open incident (appends a resolved row; the
        log stays append-only, latest row per key wins)."""
        key = (check, ticker, stage, evidence_ref)
        if key not in self.open_keys:
            return
        self.open_keys.discard(key)
        self.new.append({
            "id": f"{check}-{ticker or '-'}-{stage}-resolved-{_now()}",
            "detected_at": _now(), "check": check, "ticker": ticker,
            "stage": stage, "severity": "info", "evidence_ref": evidence_ref,
            "detail": f"resolved: {note}"[:300], "status": "resolved",
        })

    def emit(self, check: str, ticker: str, stage: str, severity: str,
             evidence_ref: str, detail: str) -> None:
        key = (check, ticker, stage, evidence_ref)
        if key in self.open_keys:
            return  # already open: no duplicate rows
        self.open_keys.add(key)
        self.new.append({
            "id": f"{check}-{ticker or '-'}-{stage}-{_now()}",
            "detected_at": _now(), "check": check, "ticker": ticker,
            "stage": stage, "severity": severity, "evidence_ref": evidence_ref,
            "detail": detail[:300], "status": "open",
        })

    def save(self) -> int:
        if not self.new:
            return 0
        self.failures_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.failures_path, "a", encoding="utf-8") as f:
            for row in self.new:
                f.write(json.dumps(row) + "\n")
        return len(self.new)


def check_w1(w: Watch) -> None:
    """Infra STOPs in team_runs."""
    con = _connect(w.data / "agent" / "team_runs.db")
    if con is None:
        return
    for r in con.execute(
        "SELECT run_id, team_name, verdict, substr(result_json,1,2000) res,"
        " substr(created_at,1,19) ts FROM team_runs WHERE verdict='STOP'"
    ):
        d = dict(r)
        blob = f"{d['verdict']} {d['res']}".lower()
        if any(k in blob for k in INFRA_KEYWORDS):
            w.emit("W1-infra-stop", "", str(d["team_name"] or ""),
                   "high", d["run_id"],
                   f"research STOP w/ infra signature at {d['ts']}")
    con.close()


def check_w2(w: Watch) -> None:
    """Fresh summaries grounded on zero angles."""
    con = _connect(w.data / "agent" / "ticker_summaries.db")
    if con is None:
        return
    try:
        rows = con.execute(
            "SELECT ticker, angles_with_data, angle_count, source_run_id,"
            " substr(updated_at,1,19) ts FROM ticker_summaries"
            " WHERE angles_with_data=0"
        ).fetchall()
    except sqlite3.Error:
        rows = []
    for r in rows:
        d = dict(r)
        w.emit("W2-zero-data-summary", d["ticker"], "summary_agent", "medium",
               f"source_run {d['source_run_id']}",
               f"{d['ticker']} summary 0/{d['angle_count']} angles with data at {d['ts']}")
    con.close()


def check_w3(w: Watch, api_key: str) -> None:
    """Watchlisted tickers with no recent daily candles (2 polls to fire)."""
    if not api_key:
        return
    try:
        wl_req = urllib.request.Request(
            "http://localhost:8081/stock/watchlist/tickers",
            headers={"Authorization": f"Bearer {api_key}"})
        wl = json.load(urllib.request.urlopen(wl_req, timeout=10)).get("tickers", [])
    except Exception:
        return
    for t in wl:
        try:
            url = (f"http://localhost:8081/stock/candles/{t}"
                   "?interval=1d&days=5&adjusted=true")
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {api_key}"})
            payload = json.load(urllib.request.urlopen(req, timeout=15))
            empty = not payload.get("data")
            hdr_empty = False
        except Exception:
            empty, hdr_empty = True, False
        if empty:
            # second consecutive poll required: a pending row from the
            # previous pass (persisted in failures.jsonl) escalates this
            # to open. Pending rows are history; the open row dedupes
            # future polls via open_keys.
            prior_pending = [f for f in w.prior
                             if f.get("check") == "W3-empty-market"
                             and f.get("ticker") == t
                             and f.get("status") == "pending"]
            if prior_pending:
                w.emit("W3-empty-market", t, "sweep_execute", "high", "",
                       f"{t} daily candles empty 2 polls in a row")
            else:
                w.new.append({
                    "id": f"W3-empty-market-{t}-pending-{_now()}",
                    "detected_at": _now(), "check": "W3-empty-market",
                    "ticker": t, "stage": "sweep_execute", "severity": "low",
                    "evidence_ref": "", "detail": "first empty poll (needs 2)",
                    "status": "pending",
                })


def check_w4(w: Watch) -> None:
    """Team runs slower than 3x baseline p50 (or 15 min with no baseline)."""
    base = _baselines()
    team_stage = {"screener": "summary_agent", "research": "sweep_execute"}
    con = _connect(w.data / "agent" / "team_runs.db")
    if con is None:
        return
    for r in con.execute(
        "SELECT run_id, team_name, status, time_used_seconds,"
        " substr(created_at,1,19) ts FROM team_runs WHERE status='done'"
    ):
        d = dict(r)
        stage = team_stage.get((d["team_name"] or "").lower(), "")
        if not stage:
            continue
        secs = float(d["time_used_seconds"] or 0)
        p50 = float((base.get(stage) or {}).get("p50_s") or 0)
        limit = 3 * p50 if p50 else 900.0
        if secs > limit:
            w.emit("W4-stage-overrun", "", stage, "medium", d["run_id"],
                   f"{d['team_name']} run {secs:.0f}s > 3x p50 ({p50:.0f}s) at {d['ts']}")
    con.close()


def check_w5(w: Watch, api_key: str) -> None:
    """Live no-auth probe on one protected route per service (auth must hold)."""
    if not api_key:
        return
    import urllib.error
    probes = [
        ("stock", "http://localhost:8081/stock/candles/AAPL?interval=1d&days=5"),
        ("features", "http://localhost:8082/features/factors"),
        ("quant-core", "http://localhost:8084/strategy/strategies"),
        ("research", "http://localhost:8087/research/sweep/recipes"),
        ("portfolio", "http://localhost:8090/portfolio/state"),
        ("agent", "http://localhost:8086/agent/broker/performance/test"),
    ]
    for svc, url in probes:
        try:
            urllib.request.urlopen(url, timeout=8)
            code = 200  # reachable WITHOUT key: enforcement missing
        except urllib.error.HTTPError as e:
            code = e.code  # 401/403 expected
        except Exception:
            continue  # service down: not an auth question (W6 covers silence)
        if code == 200:
            w.emit("W5-auth-open", "", svc, "high", url,
                   f"{svc} protected route reachable with NO key")


def check_w6(w: Watch) -> None:
    """Worker silence via heartbeats, NOT ledger rows: an idle-healthy
    worker writes no ledger rows by design (gate unchanged), so ledger
    silence is normal. What must never go quiet is the cycle heartbeat
    itself (planner/allocator "cycle complete" log lines, analysis
    latest-run age)."""
    import subprocess as _sp
    planner = _live_interval("agent-api", "VINU_AGENT_PLANNER_INTERVAL", 1800)
    allocator = _live_interval("agent-api", "VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL", 900)
    try:
        out = _sp.run(
            ["docker", "compose", "logs", "--since", "60m", "agent-api"],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
        )
        logs = out.stdout if out.returncode == 0 else ""
    except (OSError, _sp.TimeoutExpired):
        logs = ""
    import re as _re
    # docker log lines carry their own timestamps; container clock ~= host.
    def _last(marker: str):
        best = None
        for m in _re.finditer(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*" + marker, logs):
            best = m.group(1)
        if not best:
            return None
        try:
            dt = datetime.strptime(best, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds()
        except ValueError:
            return None
    for marker, interval, worker in (
        ("planner cycle complete", planner, "planner-worker"),
        ("capital-allocator cycle complete", allocator, "capital-allocator-worker"),
    ):
        gap = _last(marker)
        if gap is None:
            continue  # no log evidence either way: don't fire blind
        if gap > 2 * interval + 120:
            w.emit("W6-worker-silence", "", worker, "medium", "",
                   f"no {worker} heartbeat for {gap / 60:.0f} min (>2x {interval:.0f}s + grace)")


def check_w7(w: Watch) -> None:
    """Resource pressure: container mem >85% of its limit, sustained high
    CPU, or OOM-kill evidence (exit 137 / restart loop). An OOM-killed
    worker looks exactly like a 'stuck pipeline' from the outside -- this
    check tells the two apart. Needs the docker CLI; skipped silently
    without it."""
    import json as _json
    import subprocess as _sp
    try:
        out = _sp.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, _sp.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    for line in out.stdout.splitlines():
        try:
            s = _json.loads(line)
        except json.JSONDecodeError:
            continue
        name = str(s.get("Name", ""))
        if "vinu-components-" not in name:
            continue
        svc = name.replace("vinu-components-", "").rsplit("-1", 1)[0]
        try:
            mem_pct = float(str(s.get("MemPerc", "0%")).rstrip("%"))
        except ValueError:
            mem_pct = 0.0
        if mem_pct > 85:
            w.emit("W7-mem-pressure", "", svc, "high", f"mem {mem_pct:.0f}%",
                   f"{svc} using {s.get('MemUsage', '?')} ({mem_pct:.0f}% of limit)")
    # OOM / crash-loop evidence via compose container states
    try:
        out = _sp.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT),
        )
    except (OSError, _sp.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    for line in out.stdout.splitlines():
        try:
            c = _json.loads(line)
        except json.JSONDecodeError:
            continue
        state = str(c.get("State", "")).lower()
        name = str(c.get("Name", "") or c.get("Service", ""))
        if "vinu-components-" not in name:
            continue
        svc = name.replace("vinu-components-", "").rsplit("-1", 1)[0]
        if state not in ("running", "healthy") and "starting" not in state:
            w.emit("W7-container-down", "", svc, "high", state,
                   f"{svc} container state={state or '?'} (OOM-kill shows here as exited/OOMKilled)")


def run_once(data_dir: Path, failures: Path, with_live: bool) -> int:
    w = Watch(data_dir, failures)
    key = ""
    try:
        key = (ROOT / "secrets" / "vinu_api_key").read_text().strip()
    except OSError:
        pass
    check_w1(w)
    check_w2(w)
    if with_live:
        check_w3(w, key)
        check_w5(w, key)
    check_w4(w)
    check_w6(w)
    check_w7(w)
    n = w.save()
    if w.new:
        print(f"watchdog: {n} new incident(s):")
        for row in w.new:
            print(f"  [{row['severity']}] {row['check']} {row['ticker']}/{row['stage']}: {row['detail'][:110]}")
    else:
        print("watchdog: clean (no new incidents)")
    latest = _latest_status(_load_failures(failures))
    open_n = sum(1 for v in latest.values() if v == "open")
    print(f"open incidents total: {open_n}")
    return 1 if open_n else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="VINU pipeline failure watchdog (read-only)")
    ap.add_argument("--watch", action="store_true", help="single pass (default)")
    ap.add_argument("--daemon", action="store_true", help="loop forever")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--failures", default=str(FAILURES_FILE))
    ap.add_argument("--no-live", action="store_true", help="skip HTTP probes (offline DB-only)")
    args = ap.parse_args()
    if args.daemon:
        while True:
            run_once(Path(args.data), Path(args.failures), not args.no_live)
            time.sleep(args.interval)
    else:
        return run_once(Path(args.data), Path(args.failures), not args.no_live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
