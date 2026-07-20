"""Drive one ticker through the analysis pipeline end to end:

    vinu-stock-price -> vinu-news -> vinu-tools (features) -> vinu-initial-analysis
    -> vinu-strategy -> vinu-simulator -> vinu-research

and record, per step: wall-clock duration, container memory usage, and (for the
news/research steps) every local-LLM call made — model, prompt, response, latency.

Deliberately stops at vinu-research. vinu-portfolio/vinu-agent/vinu-live (anything
that would touch a broker) are out of scope and never called.

Requires the relevant docker-compose services to already be running:

    docker compose up -d news-ingest news-api stock-ingest stock-api \\
        features-worker features-api initial-analysis-compute initial-analysis-api \\
        strategy-api simulator-api research-api

Usage:
    python run_pipeline.py --ticker AAPL --from-date 2024-01-01 --to-date 2024-06-01
"""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parent

SERVICES: dict[str, dict[str, Any]] = {
    "stock_price": {"base_url": "http://127.0.0.1:8081", "compose_service": "stock-api", "data_subdir": None},
    "news": {"base_url": "http://127.0.0.1:8080", "compose_service": "news-api", "data_subdir": "news"},
    "features": {"base_url": "http://127.0.0.1:8082", "compose_service": "features-api", "data_subdir": None},
    "initial_analysis": {"base_url": "http://127.0.0.1:8083", "compose_service": "initial-analysis-api", "data_subdir": None},
    "strategy": {"base_url": "http://127.0.0.1:8084", "compose_service": "strategy-api", "data_subdir": None},
    "simulator": {"base_url": "http://127.0.0.1:8085", "compose_service": "simulator-api", "data_subdir": None},
    "research": {"base_url": "http://127.0.0.1:8087", "compose_service": "research-api", "data_subdir": "research"},
}


@dataclass
class StepResult:
    name: str
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    duration_sec: float | None = None
    memory_start_mb: float | None = None
    memory_peak_mb: float | None = None
    memory_end_mb: float | None = None
    response_summary: Any = None
    llm_calls: list[dict] = field(default_factory=list)
    error: str | None = None


# --- infrastructure helpers -------------------------------------------------

def resolve_container_id(compose_service: str) -> str | None:
    try:
        out = subprocess.run(
            ["docker", "compose", "ps", "-q", compose_service],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        cid = out.stdout.strip().splitlines()
        return cid[0] if cid else None
    except (OSError, subprocess.SubprocessError):
        return None


def _parse_mem_usage(raw: str) -> float | None:
    """Parse docker stats --format "{{.MemUsage}}" ("123.4MiB / 512MiB") to MiB."""
    try:
        used = raw.split("/")[0].strip()
        num = "".join(ch for ch in used if ch.isdigit() or ch == ".")
        if not num:
            return None
        value = float(num)
        if "GiB" in used or "GB" in used:
            value *= 1024
        return value
    except (ValueError, IndexError):
        return None


class MemorySampler:
    """Polls `docker stats` for one container in the background while a step runs."""

    def __init__(self, container_id: str | None, interval: float = 0.5) -> None:
        self._container_id = container_id
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.start_mb: float | None = None
        self.peak_mb: float | None = None
        self.end_mb: float | None = None

    def _sample(self) -> float | None:
        if not self._container_id:
            return None
        try:
            out = subprocess.run(
                ["docker", "stats", self._container_id, "--no-stream", "--format", "{{.MemUsage}}"],
                capture_output=True, text=True, timeout=5,
            )
            return _parse_mem_usage(out.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return None

    def _run(self) -> None:
        while not self._stop.is_set():
            val = self._sample()
            if val is not None:
                self.peak_mb = val if self.peak_mb is None else max(self.peak_mb, val)
                self.end_mb = val
            self._stop.wait(self._interval)

    def start(self) -> None:
        self.start_mb = self._sample()
        self.peak_mb = self.start_mb
        self.end_mb = self.start_mb
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        final = self._sample()
        if final is not None:
            self.end_mb = final
            self.peak_mb = final if self.peak_mb is None else max(self.peak_mb, final)


def collect_llm_calls(data_subdir: str | None, since_ts: str, until_ts: str) -> list[dict]:
    if not data_subdir:
        return []
    path = ROOT / "data" / data_subdir / "llm_calls.jsonl"
    if not path.exists():
        return []
    calls = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = entry.get("ts", "")
            if since_ts <= ts <= until_ts:
                calls.append(entry)
    return calls


def wait_for_ready(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code < 500:
                return
        except requests.RequestException as exc:
            last_exc = exc
        time.sleep(1)
    raise RuntimeError(f"Service not ready at {url} after {timeout}s: {last_exc}")


def _date_to_epoch(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _poll_job(base_url: str, job_id: str, timeout: float = 180.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(f"{base_url}/backfill/status/{job_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") in ("done", "completed", "finished", "error", "failed"):
            return data
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} on {base_url} did not finish within {timeout}s")


def run_step(name: str, service_key: str, probe_path: str, work_fn: Callable[[], Any]) -> StepResult:
    svc = SERVICES[service_key]
    result = StepResult(name=name)
    print(f"\n=== {name} ===")

    container_id = resolve_container_id(svc["compose_service"])
    sampler = MemorySampler(container_id)

    result.started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    sampler.start()
    try:
        wait_for_ready(svc["base_url"] + probe_path)
        result.response_summary = work_fn()
        result.status = "ok"
    except Exception as exc:
        result.status = "error"
        result.error = str(exc)
    finally:
        sampler.stop()
        result.duration_sec = round(time.perf_counter() - start, 3)
        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.memory_start_mb = sampler.start_mb
        result.memory_peak_mb = sampler.peak_mb
        result.memory_end_mb = sampler.end_mb
        result.llm_calls = collect_llm_calls(svc["data_subdir"], result.started_at, result.finished_at)

    icon = "OK" if result.status == "ok" else "FAILED"
    print(
        f"[{icon}] {name}: {result.duration_sec}s, "
        f"mem {result.memory_start_mb}->{result.memory_peak_mb}->{result.memory_end_mb} MiB, "
        f"{len(result.llm_calls)} llm call(s)"
    )
    if result.error:
        print(f"  error: {result.error}")
    return result


# --- stage implementations --------------------------------------------------

def step_stock_price(ticker: str) -> dict:
    base = SERVICES["stock_price"]["base_url"]
    requests.post(f"{base}/watchlist/tickers", json={"tickers": [ticker]}, timeout=30).raise_for_status()

    resp = requests.post(f"{base}/backfill/trigger", timeout=30)
    resp.raise_for_status()
    job_id = resp.json().get("summary", {}).get("job_id")
    backfill_result = _poll_job(base, job_id) if job_id else None

    resp = requests.post(f"{base}/ingest/trigger", timeout=30)
    resp.raise_for_status()
    job_id = resp.json().get("summary", {}).get("job_id")
    ingest_result = _poll_job(base, job_id) if job_id else None

    return {"backfill": backfill_result, "ingest": ingest_result}


def step_news(ticker: str, article_count: int, wait_sec: float = 180.0) -> dict:
    base = SERVICES["news"]["base_url"]
    # Toggling backfill on already kicks off news-ingest's background fetch for this
    # ticker (a real, possibly multi-year historical sweep that can take many minutes) —
    # calling /backfill/trigger here too would just block on that same slow work a
    # second time. Poll for articles instead, with a bounded wait, and proceed with
    # whatever's arrived so far rather than requiring the full historical sweep to finish.
    requests.post(f"{base}/backfill/{ticker}/toggle", json={"enabled": True}, timeout=30).raise_for_status()

    articles: list[dict] = []
    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        resp = requests.get(f"{base}/ticker/{ticker}", params={"days": 7, "limit": article_count}, timeout=30)
        resp.raise_for_status()
        articles = resp.json().get("data", [])
        if articles:
            break
        time.sleep(5)

    analyzed = 0
    for article in articles[:article_count]:
        url_or_id = article.get("url") or article.get("id")
        if not url_or_id:
            continue
        r = requests.post(f"{base}/news/analyze", json={"url_or_id": url_or_id}, timeout=300)
        if r.status_code == 200:
            analyzed += 1

    return {"articles_found": len(articles), "articles_analyzed": analyzed}


def step_features(ticker: str, from_ts: int, to_ts: int, features: list[str]) -> dict:
    base = SERVICES["features"]["base_url"]
    body = {
        "title": f"pipeline-run-{ticker}",
        "symbols": [ticker],
        "from_ts": from_ts,
        "to_ts": to_ts,
        "interval": "1d",
        "features": features,
        "run_immediately": True,
    }
    resp = requests.post(f"{base}/requests", json=body, timeout=180)
    resp.raise_for_status()
    return resp.json()


def step_initial_analysis(ticker: str, from_ts: int, to_ts: int) -> dict:
    # Computing all 25 deterministic angles for one ticker is genuinely slow
    # (observed ~8 minutes end to end) — not a hang, just a lot of work.
    base = SERVICES["initial_analysis"]["base_url"]
    resp = requests.post(f"{base}/run/{ticker}", params={"from_ts": from_ts, "to_ts": to_ts}, timeout=900)
    resp.raise_for_status()
    return resp.json()


def step_strategy(ticker: str, strategy_name: str | None, holder: dict) -> dict:
    base = SERVICES["strategy"]["base_url"]
    if not strategy_name:
        resp = requests.get(f"{base}/strategies", timeout=30)
        resp.raise_for_status()
        names = resp.json()
        if not names:
            raise RuntimeError("No strategies available from GET /strategies")
        strategy_name = names[0]["name"] if isinstance(names[0], dict) else names[0]

    resp = requests.post(
        f"{base}/strategies/{strategy_name}/evaluate", params={"symbols": ticker}, timeout=120
    )
    resp.raise_for_status()
    holder["strategy_name"] = strategy_name
    return resp.json()


_CUSTOM_STRATEGY_CODE = """
from vinu_simulator.engine.strategies import BaseStrategy


class SmaCrossover(BaseStrategy):
    def generate_weights(self, data):
        fast = data["close"].rolling(9).mean()
        slow = data["close"].rolling(21).mean()
        return (fast > slow).astype(float)
"""


def step_simulator(ticker: str, from_date: str, to_date: str) -> dict:
    # /simulate reads pre-accumulated historical weight data from repeated daily
    # `evaluate` calls (production strategies get "warmed up" over weeks of real
    # runs) — a freshly-evaluated symbol has none, so it 422s with "No weight data
    # found". /simulate/custom instead computes weights on the fly for any date
    # range from an ad-hoc BaseStrategy subclass, which is what an on-demand run
    # like this needs. Mirrors vinu-strategy's built-in "ma_crossover" (9/21 SMA).
    base = SERVICES["simulator"]["base_url"]
    body = {
        "symbols": [ticker],
        "strategy_code": _CUSTOM_STRATEGY_CODE,
        "class_name": "SmaCrossover",
        "start_date": from_date,
        "end_date": to_date,
    }
    resp = requests.post(f"{base}/simulate/custom", json=body, timeout=300)
    resp.raise_for_status()
    return resp.json()


def step_research(ticker: str, from_date: str, to_date: str) -> dict:
    base = SERVICES["research"]["base_url"]
    body = {"symbol": ticker, "from_date": from_date, "to_date": to_date, "dry_run": False}
    resp = requests.post(f"{base}/research/run", json=body, timeout=1800)
    resp.raise_for_status()
    return resp.json()


# --- orchestration -----------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a ticker through the vinu-components analysis pipeline "
        "(stock-price -> news -> features -> initial-analysis -> strategy -> "
        "simulator -> research) and log timing/memory/LLM data per step."
    )
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--from-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--strategy-name", default=None, help="Defaults to the first strategy returned by GET /strategies")
    parser.add_argument("--news-articles", type=int, default=5, help="How many recent articles to run LLM analysis on")
    parser.add_argument("--features", default="sma_20,rsi_14", help="Comma-separated feature kinds to compute")
    parser.add_argument("--verbose", action="store_true", help="Print each LLM call's prompt/response")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    from_ts = _date_to_epoch(args.from_date)
    to_ts = _date_to_epoch(args.to_date)
    feature_list = [f.strip() for f in args.features.split(",") if f.strip()]
    run_id = f"{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    holder: dict[str, Any] = {"strategy_name": args.strategy_name}
    steps: list[StepResult] = []

    def prev_ok() -> bool:
        return bool(steps) and steps[-1].status == "ok"

    steps.append(run_step("vinu-stock-price", "stock_price", "/health", lambda: step_stock_price(ticker)))

    if prev_ok():
        steps.append(run_step("vinu-news", "news", "/health", lambda: step_news(ticker, args.news_articles)))
    else:
        steps.append(StepResult(name="vinu-news", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-tools (features)", "features", "/health",
            lambda: step_features(ticker, from_ts, to_ts, feature_list),
        ))
    else:
        steps.append(StepResult(name="vinu-tools (features)", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-initial-analysis", "initial_analysis", "/symbols",
            lambda: step_initial_analysis(ticker, from_ts, to_ts),
        ))
    else:
        steps.append(StepResult(name="vinu-initial-analysis", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-strategy", "strategy", "/health",
            lambda: step_strategy(ticker, holder["strategy_name"], holder),
        ))
    else:
        steps.append(StepResult(name="vinu-strategy", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-simulator", "simulator", "/health",
            lambda: step_simulator(ticker, args.from_date, args.to_date),
        ))
    else:
        steps.append(StepResult(name="vinu-simulator", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-research", "research", "/health",
            lambda: step_research(ticker, args.from_date, args.to_date),
        ))
    else:
        steps.append(StepResult(name="vinu-research", status="skipped"))

    report = {
        "run_id": run_id,
        "ticker": ticker,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "started_at": steps[0].started_at if steps else None,
        "finished_at": steps[-1].finished_at if steps else None,
        "steps": [asdict(s) for s in steps],
    }

    out_dir = ROOT / "logs" / "pipeline_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"\n=== Summary: {ticker} ===")
    for s in steps:
        dur = f"{s.duration_sec:>8.2f}s" if s.duration_sec is not None else " " * 8 + "-"
        print(
            f"{s.name:28s} {s.status:8s} {dur}  "
            f"mem {s.memory_start_mb}->{s.memory_peak_mb}->{s.memory_end_mb} MiB  "
            f"llm_calls={len(s.llm_calls)}"
        )
        if args.verbose:
            for call in s.llm_calls:
                print(f"    [{call['event']}] model={call['model']} duration={call['duration_sec']}s")
                print(f"    system: {str(call['system_prompt'])[:200]}")
                print(f"    user:   {str(call['user_prompt'])[:200]}")
                print(f"    resp:   {str(call['response'])[:200]}")

    print(f"\nFull report written to {out_path}")


if __name__ == "__main__":
    main()
