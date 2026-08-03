#!/usr/bin/env python3
"""Day-stepper replay harness for the 1-month agentic back-test.

Drives the real `vinu-agent` HTTP API one simulated trading day at a time,
advancing `as_of` per the plan's simulated-clock design. It does NOT
reimplement any agent logic — a tied-down step calls the same
POST /agent/sessions and POST /agent/sessions/{id}/messages endpoints a
real user/cron job would use. Each day's thinking (full ordered tool
trace), final response, and account snapshot are written separately under
`the-1-month-back-testing/results/<run-id>/<date>/`.

Replay discipline (from the plan):
  - reuse ONE session across the whole month (agent keeps memory of its own
    prior decisions and losses);
  - fixed daily prompt, never changed day to day;
  - strictly sequential, one day at a time (project SQLite/WAL constraint);
  - resumable: output of a completed day is never overwritten and a fresh
    invocation skips already-completed days.

The agent accepts `as_of` on CreateSessionRequest and SendMessageRequest
and persists it into `session.config["as_of"]`; tools read it as `_as_of`
(replay-mode lookahead clamp + historical-fill broker, see items 1-2).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("replay")

TICKERS = ["AAPL", "TSLA", "JNJ"]
ET_TZ = ZoneInfo("America/New_York")

DEFAULT_AGENT_API = "http://localhost:8086/agent"
_ROOT = Path(__file__).resolve().parents[3]  # workspace root
DEFAULT_DATA_ROOT = _ROOT / "vinu-components" / "data" / "agent"
RESULTS_BASE = _ROOT / "the-1-month-back-testing" / "results"

PROMPT_TEMPLATE = (
    "It's the start of the trading session on {date}. Review your current "
    "positions, account state, and any relevant signals for AAPL, TSLA, and "
    "JNJ. Decide what action, if any, to take today, and explain your "
    "reasoning before acting."
)

MAX_WAIT_SEC = 60 * 30  # 30 min per day (local 35B LLM can be slow)
POLL_SEC = 2.0


def trading_days(start: str, end: str) -> list[str]:
    """Weekday-only calendar between start..end inclusive (no holiday table;
    the validated window 2026-07-06..31 has no US market holiday inside)."""
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    days = []
    d = s
    while d <= e:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d = datetime.fromisoformat(d.isoformat()).date() + __import__(
            "datetime"
        ).timedelta(days=1)
    return days


def as_of_for(day: str) -> str:
    """Decision point = 09:30 ET (regular-session open) as UTC ISO."""
    naive = datetime.fromisoformat(f"{day}T09:30:00")
    local = naive.replace(tzinfo=ET_TZ)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_action(content: str) -> dict:
    """Best-effort structured summary of the final decision from its text.

    Deliberately narrow: generic vocabulary like "closing price" or "close
    to" must not be mistaken for "close the position", or every day's price
    recap gets mislabeled as a trade (found 2026-08-03 reviewing
    run-2026-07-06-2026-07-31-v2 — the old broad `close|exit|reduce` word
    list matched "Latest close: 308.43" on a pure no-op day). This is a
    narrative aid only; the trade log / P&L come from the broker's real
    ledger, never from this parse.
    """
    txt = content or ""
    summary: dict = {"action": "none", "symbol": None, "qty": None, "side": None}
    lower = txt.lower()
    buy_re = re.compile(r"\b(bought|buying|i(?:'ll| will)?\s*buy|submit(?:ted|ting)?\s+(?:a\s+)?buy)\b")
    sell_re = re.compile(r"\b(sold|selling|i(?:'ll| will)?\s*sell|close(?:d|ing)?\s+(?:the|my|out)\s+position|exit(?:ed|ing)?\s+(?:the|my)\s+position|reduc(?:e|ed|ing)\s+(?:the|my)\s+position)\b")
    if buy_re.search(lower):
        summary["action"] = "trade"
        summary["side"] = "buy"
    if sell_re.search(lower):
        summary["action"] = "trade"
        summary["side"] = "sell"
    sym = re.search(r"\b(AAPL|TSLA|JNJ)\b", txt)
    if sym:
        summary["symbol"] = sym.group(1)
    qty = re.search(r"\b(\d{1,5})\s*shares?\b", lower)
    if qty:
        summary["qty"] = int(qty.group(1))
    summary["reasoning_excerpt"] = txt[:2500]
    return summary


class ReplayRunner:
    def __init__(
        self,
        api: str,
        data_root: Path,
        run_dir: Path,
        session_id: str | None = None,
    ) -> None:
        self.api = api.rstrip("/")
        self.data_root = data_root
        self.run_dir = run_dir
        self.session_id = session_id
        self._model = None
        self._runtime = api

    # -- HTTP -----------------------------------------------------------------
    def _sessions_url(self, *parts: str) -> str:
        return "/".join([self.api, "sessions", *parts]).rstrip("/")

    def create_session(self, first_day: str) -> str:
        r = requests.post(
            self._sessions_url(),
            json={"title": f"one-month-replay-{first_day}", "as_of": as_of_for(first_day)},
            timeout=30,
        )
        r.raise_for_status()
        self.session_id = r.json()["session_id"]
        log.info("Created replay session %s", self.session_id)
        return self.session_id

    def send_message(self, content: str, as_of: str) -> tuple[str, str]:
        r = requests.post(
            self._sessions_url(self.session_id, "messages"),
            json={"content": content, "as_of": as_of},
            timeout=30,
        )
        r.raise_for_status()
        j = r.json()
        return j["message_id"], j["attempt_id"]

    def wait_for_attempt(self, attempt_id: str) -> dict:
        """Poll messages until the assistant reply linked to this attempt lands,
        then read the persisted attempt file (holding the full react trace)."""
        deadline = time.time() + MAX_WAIT_SEC
        while time.time() < deadline:
            r = requests.get(
                self._sessions_url(self.session_id, "messages"),
                params={"limit": 200},
                timeout=30,
            )
            r.raise_for_status()
            full = r.json()
            done = [m for m in full if m.get("linked_attempt_id") == attempt_id]
            if done:
                attempt_file = (
                    self.data_root
                    / "sessions"
                    / self.session_id
                    / "attempts"
                    / attempt_id
                    / "attempt.json"
                )
                # wait until the full react_trace has been persisted (there is a
                # brief window where messages.jsonl is appended before attempt.json)
                deadline_trace = time.time() + 60
                while time.time() < deadline_trace:
                    if attempt_file.exists():
                        blob = json.loads(attempt_file.read_text("utf-8"))
                        if blob.get("react_trace"):
                            return blob
                        if blob.get("status") == "completed":
                            return blob
                    time.sleep(0.5)
                if attempt_file.exists():
                    return json.loads(attempt_file.read_text("utf-8"))
                # fall back to the assistant message content
                return {"status": "completed", "assistant": done[-1]["content"]}
            time.sleep(POLL_SEC)
        raise TimeoutError(f"attempt {attempt_id} not completed within timeout")

    def last_account_snapshot(self) -> dict:
        """Read the historical broker's persisted ledger for this session.

        Bug-4 (found 2026-08-03): this used to fall back to {"cash": None,
        ...} when no state file existed yet, which is indistinguishable from
        "the state file is broken/missing for a real reason" — a day with
        zero trades looked identical to a read failure. The correct
        "no trades yet" state is the untouched starting balance, matching
        HistoricalFillBroker's own DEFAULT_INITIAL_CASH so a report never has
        to guess which case it's in.
        """
        state_file = self.data_root / "replay_state" / f"{self.session_id}.json"
        if state_file.exists():
            return json.loads(state_file.read_text("utf-8"))
        try:
            from vinu_agent.broker.historical_broker import DEFAULT_INITIAL_CASH
        except ImportError:
            DEFAULT_INITIAL_CASH = 100_000.0
        return {
            "cash": DEFAULT_INITIAL_CASH,
            "positions": {},
            "orders": [],
            "ledger": [],
            "note": "no trades yet this session — untouched starting balance",
        }

    def get_status(self) -> dict:
        try:
            r = requests.get(f"{self.api}/health", timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    # -- output ----------------------------------------------------------------
    def write_day(self, day: str, attempt: dict, account: dict) -> None:
        out = self.run_dir / day
        out.mkdir(parents=True, exist_ok=True)

        trace = attempt.get("react_trace") or attempt.get("assistant")
        if isinstance(trace, list):
            thinking = trace
        else:
            thinking = [{"role": "assistant", "content": trace}]
        (out / "thinking.json").write_text(
            json.dumps(thinking, indent=2, default=str), "utf-8"
        )

        final = ""
        for step in reversed(thinking):
            if isinstance(step, dict) and step.get("role") == "assistant":
                final = step.get("content") or ""
                if final:
                    break
        resp = {
            "date": day,
            "final_content": final,
            "summary": _parse_action(final),
        }
        (out / "response.json").write_text(
            json.dumps(resp, indent=2, default=str), "utf-8"
        )
        (out / "account_snapshot.json").write_text(
            json.dumps(account, indent=2, default=str), "utf-8"
        )
        log.info("wrote %s (trace %d steps)", day, len(thinking) if isinstance(thinking, list) else 1)

    def write_manifest(self, window_start: str, window_end: str, days: list[str]) -> None:
        (self.run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": self.run_dir.name,
                    "tickers": TICKERS,
                    "confirmed_window": {"start": window_start, "end": window_end},
                    "days": days,
                    "prompt_template": PROMPT_TEMPLATE,
                    "model": self._model,
                    "runtime": self.get_llm_health(),
                },
                indent=2,
            ),
            "utf-8",
        )

    def get_llm_health(self) -> dict:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2026-07-06", help="first trading day (YYYY-MM-DD)")
    ap.add_argument("--end", default="2026-07-31", help="last trading day (YYYY-MM-DD)")
    ap.add_argument("--run-id", default=None, help="results folder id (default: auto)")
    ap.add_argument("--api", default=DEFAULT_AGENT_API, help="vinu-agent API base")
    ap.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT), help="host data/agent path")
    ap.add_argument("--session", default=None, help="resume with an existing session id")
    args = ap.parse_args()

    data_root = Path(args.data_root)
    run_id = args.run_id or f"run-{args.start}-{args.end}"
    run_dir = RESULTS_BASE / run_id

    days = trading_days(args.start, args.end or args.start)
    if not days:
        log.error("no days in window %s..%s", args.start, args.end)
        return 1
    log.info("window %s..%s => %d trading days", args.start, args.end, len(days))
    log.info("results -> %s", run_dir)

    runner = ReplayRunner(args.api, data_root, run_dir, session_id=args.session)
    health = runner.get_status()
    if health.get("error"):
        log.error("agent api not reachable: %s", health["error"])
        return 1

    if args.session:
        runner.session_id = args.session
    else:
        runner.create_session(days[0])

    runner.run_dir.mkdir(parents=True, exist_ok=True)

    # resume-skip already-completed days
    todo = []
    for day in days:
        if day and (run_dir / day / "response.json").exists():
            log.info("skip already-done day %s", day)
            continue
        todo.append(day)

    runner.write_manifest(args.start, args.end, days)

    for day in todo:
        log.info("=== day %s (as_of %s) ===", day, as_of_for(day))
        msg_id, attempt_id = runner.send_message(PROMPT_TEMPLATE.format(date=day), as_of_for(day))
        try:
            attempt = runner.wait_for_attempt(attempt_id)
        except TimeoutError as e:
            log.error("%s", e)
            return 1
        account = runner.last_account_snapshot()
        runner.write_day(day, attempt, account)

    log.info("replay complete -> %s", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())