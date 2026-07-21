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
from concurrent.futures import ThreadPoolExecutor
import json
import re
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


def _retry(fn: Callable[[], requests.Response], retries: int = 3, base_delay: float = 1.0) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if attempt == retries - 1:
                break
            delay = base_delay * 2 ** attempt
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise
            last_exc = e
            if attempt == retries - 1:
                break
            delay = base_delay * 2 ** attempt
        _log("⟳", f"retry {attempt+1}/{retries} after {delay:.1f}s: {last_exc}")
        time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _date_to_epoch(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _poll_job(base_url: str, job_id: str, timeout: float = 180.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = _retry(lambda: requests.get(f"{base_url}/backfill/status/{job_id}", timeout=10))
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") in ("done", "completed", "finished", "error", "failed"):
            return data
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} on {base_url} did not finish within {timeout}s")


_VERBOSE = False


def _log(marker: str, msg: str, *args: Any) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {marker} {msg}")


def _req(method: str, url: str, **kwargs: Any) -> requests.Response:
    start = time.perf_counter()
    try:
        resp = _retry(lambda: requests.request(method, url, **kwargs))
        elapsed = time.perf_counter() - start
        icon = "✓" if resp.status_code < 400 else "✗"
        if _VERBOSE:
            _log(icon, f"{method} {url} ({resp.status_code}, {elapsed:.1f}s)")
        return resp
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
        elapsed = time.perf_counter() - start
        if _VERBOSE:
            _log("✗", f"{method} {url} ({elapsed:.1f}s) — FAILED")
        raise


def run_step(name: str, service_key: str, probe_path: str, work_fn: Callable[[], Any]) -> StepResult:
    svc = SERVICES[service_key]
    result = StepResult(name=name)
    _log("▶", f"=== {name} ===")

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

    icon = "✓" if result.status == "ok" else "✗"
    _log(icon, f"{name}: {result.duration_sec}s, "
        f"mem {result.memory_start_mb}->{result.memory_peak_mb}->{result.memory_end_mb} MiB, "
        f"{len(result.llm_calls)} llm call(s)")
    if result.error:
        _log("✗", f"  error: {result.error}")

    if _VERBOSE and result.llm_calls:
        for c in result.llm_calls:
            print(f"  LLM [{c.get('model','?')}] {c.get('duration_sec',0):.1f}s "
                  f"{'✓' if c.get('success') else '✗'}")
            print(f"    system: {c.get('system_prompt','')[:120]}...")
            print(f"    user:   {c.get('user_prompt','')[:120]}...")
            if c.get('response'):
                print(f"    resp:   {json.dumps(c['response'], ensure_ascii=False)[:200]}")
            if c.get('error'):
                print(f"    error:  {c['error'][:200]}")
    return result


# --- stage implementations --------------------------------------------------

def step_stock_price(ticker: str, force: bool = False) -> dict:
    base = SERVICES["stock_price"]["base_url"]
    _req("POST", f"{base}/watchlist/tickers", json={"tickers": [ticker]}, timeout=30)

    body = {"symbols": [ticker]}
    if force:
        body["force"] = True

    def _trigger_and_poll(endpoint: str, label: str) -> dict | None:
        resp = _req("POST", f"{base}/{endpoint}/trigger", json=body if endpoint == "backfill" else None, timeout=30)

        if resp.status_code == 409:
            detail = resp.json().get("detail", "")
            m = re.search(r"job_id=(\w+)", detail)
            if m:
                job_id = m.group(1)
                _log("⟳", f"{label} already running — polling existing job {job_id}")
                return _poll_job(base, job_id)
            raise RuntimeError(f"{label} already running but no job_id in response: {detail}")

        job_id = resp.json().get("summary", {}).get("job_id")
        if not job_id:
            raise RuntimeError(f"{endpoint}/trigger returned no job_id")
        return _poll_job(base, job_id)

    backfill_result = _trigger_and_poll("backfill", "Backfill")
    ingest_result = _trigger_and_poll("ingest", "Ingest")

    return {"backfill": backfill_result, "ingest": ingest_result}


def step_news(ticker: str, article_count: int, wait_sec: float = 180.0) -> dict:
    base = SERVICES["news"]["base_url"]
    # Toggling backfill on already kicks off news-ingest's background fetch for this
    # ticker (a real, possibly multi-year historical sweep that can take many minutes) —
    # calling /backfill/trigger here too would just block on that same slow work a
    # second time. Poll for articles instead, with a bounded wait, and proceed with
    # whatever's arrived so far rather than requiring the full historical sweep to finish.
    _req("POST", f"{base}/backfill/{ticker}/toggle", json={"enabled": True}, timeout=30)

    articles: list[dict] = []
    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        resp = _req("GET", f"{base}/ticker/{ticker}", params={"days": 7, "limit": article_count}, timeout=30)
        articles = resp.json().get("data", [])
        if articles:
            break
        time.sleep(5)

    def _analyze_one(article: dict) -> bool:
        url_or_id = article.get("url") or article.get("id")
        if not url_or_id:
            return False
        try:
            _req("POST", f"{base}/news/analyze", json={"url_or_id": url_or_id}, timeout=300)
            return True
        except requests.RequestException:
            _log("✗", f"news/analyze failed for {url_or_id}")
            return False

    targets = [a for a in articles[:article_count] if a.get("url") or a.get("id")]
    with ThreadPoolExecutor(max_workers=min(5, len(targets))) as pool:
        results = list(pool.map(_analyze_one, targets))
    analyzed = sum(1 for r in results if r)

    return {"articles_found": len(articles), "articles_analyzed": analyzed}


def step_features(ticker: str, from_ts: int, to_ts: int, features: list[str], timeframe: str = "1d") -> dict:
    base = SERVICES["features"]["base_url"]
    body = {
        "title": f"pipeline-run-{ticker}",
        "symbols": [ticker],
        "from_ts": from_ts,
        "to_ts": to_ts,
        "interval": timeframe,
        "features": features,
        "run_immediately": True,
    }
    resp = _req("POST", f"{base}/requests", json=body, timeout=180)
    return resp.json()


def step_initial_analysis(ticker: str, from_ts: int, to_ts: int) -> dict:
    # Computing all 25 deterministic angles for one ticker is genuinely slow
    # (observed ~8 minutes end to end) — not a hang, just a lot of work.
    base = SERVICES["initial_analysis"]["base_url"]
    resp = _req("POST", f"{base}/run/{ticker}", params={"from_ts": from_ts, "to_ts": to_ts}, timeout=900)
    return resp.json()


def step_strategy(ticker: str, strategy_name: str | None, holder: dict) -> dict:
    base = SERVICES["strategy"]["base_url"]
    if not strategy_name:
        resp = _req("GET", f"{base}/strategies", timeout=30)
        names = resp.json()
        if not names:
            raise RuntimeError("No strategies available from GET /strategies")
        strategy_name = names[0]["name"] if isinstance(names[0], dict) else names[0]

    resp = _req("POST", f"{base}/strategies/{strategy_name}/evaluate", params={"symbols": ticker}, timeout=120)
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


def step_simulator(ticker: str, from_date: str, to_date: str, timeframe: str = "1d") -> dict:
    base = SERVICES["simulator"]["base_url"]
    body = {
        "symbols": [ticker],
        "strategy_code": _CUSTOM_STRATEGY_CODE,
        "class_name": "SmaCrossover",
        "start_date": from_date,
        "end_date": to_date,
        "interval": timeframe,
    }
    resp = _req("POST", f"{base}/simulate/custom", json=body, timeout=300)
    return resp.json()


def step_research(ticker: str, from_date: str, to_date: str, model: str | None = None, strategy_code: str | None = None) -> dict:
    base = SERVICES["research"]["base_url"]
    body = {
        "symbol": ticker,
        "from_date": from_date,
        "to_date": to_date,
        "dry_run": False,
        "user_idea": "Pipeline auto-run — SMA crossover baseline",
    }
    if strategy_code:
        body["strategy_code"] = strategy_code
    resp = _req("POST", f"{base}/research/run", json=body, timeout=1800)
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
    parser.add_argument("--timeframe", default="1d", choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                        help="Bar interval for analysis (default: 1d)")
    parser.add_argument("--model", default=None, help="LLM model to use (e.g., qwen36-35B)")
    parser.add_argument("--verbose", action="store_true", help="Print each API call and LLM call in real time")
    parser.add_argument("--force", action="store_true", help="Force re-backfill even if symbol already complete")
    args = parser.parse_args()

    global _VERBOSE
    _VERBOSE = args.verbose
    tf = args.timeframe

    ticker = args.ticker.upper()
    from_ts = _date_to_epoch(args.from_date)
    to_ts = _date_to_epoch(args.to_date)
    feature_list = [f.strip() for f in args.features.split(",") if f.strip()]
    run_id = f"{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    holder: dict[str, Any] = {"strategy_name": args.strategy_name}
    steps: list[StepResult] = []

    def prev_ok() -> bool:
        return bool(steps) and steps[-1].status == "ok"

    steps.append(run_step("vinu-stock-price", "stock_price", "/health", lambda: step_stock_price(ticker, force=args.force)))

    if prev_ok():
        steps.append(run_step("vinu-news", "news", "/health", lambda: step_news(ticker, args.news_articles)))
    else:
        steps.append(StepResult(name="vinu-news", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-tools (features)", "features", "/health",
            lambda: step_features(ticker, from_ts, to_ts, feature_list, timeframe=tf),
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
            lambda: step_simulator(ticker, args.from_date, args.to_date, timeframe=tf),
        ))
    else:
        steps.append(StepResult(name="vinu-simulator", status="skipped"))

    if prev_ok():
        steps.append(run_step(
            "vinu-research", "research", "/health",
            lambda: step_research(ticker, args.from_date, args.to_date, model=args.model, strategy_code=_CUSTOM_STRATEGY_CODE),
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
