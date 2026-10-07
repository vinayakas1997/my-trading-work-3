"""The queue in motion: callers submit an OpenAI-style chat request and wait on the same HTTP connection; one worker
takes the most urgent row, calls the model server, and hands the reply back unchanged.

Because the gateway speaks the OpenAI protocol, a caller changes only its base URL (and says who it is with
`X-Vinu-Caller` / `X-Vinu-Purpose` headers); nothing about its own request or response handling changes.

A caller that hangs up (timeout, crash) cancels its row: a queued row is dropped, a running call is aborted, so an
abandoned request can no longer keep the model's only slot busy.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from vinu_infra.secrets_loader import load_secret
from vinu_llm_gateway.priorities import UnknownPurpose, resolve_purpose
from vinu_llm_gateway.store import QueueStore, dedupe_key

LOG = logging.getLogger("vinu_llm_gateway")

_TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}
STALL_STREAK = 2    # this many timeouts in a row means a stalled model server: later timeouts are not retried


@dataclass
class GatewayConfig:
    upstream_url: str = "http://host.docker.internal:8092/v1"
    provider: str = "openai"
    api_key_ref: str = ""                 # NAME of a secret file; empty = the upstream needs no key
    default_max_tokens: int = 8000
    attempt_timeout_sec: float = 300.0    # one call to the model
    deadline_sec: float = 1800.0          # a row still queued after this is dropped
    max_attempts: int = 3
    age_step_sec: float = 300.0           # a waiting row gains one priority level per this long
    sweep_every_sec: float = 15.0
    undelivered_after_sec: float = 600.0
    history_json_days: float = 7.0
    db_path: str = "data/llm_gateway.db"

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        e = os.environ.get
        return cls(
            upstream_url=e("VINU_LLM_UPSTREAM_URL", cls.upstream_url),
            api_key_ref=e("VINU_LLM_UPSTREAM_KEY_REF", ""),
            default_max_tokens=int(e("VINU_LLM_MAX_TOKENS", "8000")),
            attempt_timeout_sec=float(e("VINU_LLM_GATEWAY_ATTEMPT_TIMEOUT_SEC", "300")),
            deadline_sec=float(e("VINU_LLM_GATEWAY_DEADLINE_SEC", "1800")),
            max_attempts=int(e("VINU_LLM_GATEWAY_MAX_ATTEMPTS", "3")),
            age_step_sec=float(e("VINU_LLM_GATEWAY_AGE_STEP_SEC", "300")),
            history_json_days=float(e("VINU_LLM_GATEWAY_HISTORY_JSON_DAYS", "7")),
            db_path=os.path.join(e("VINU_LLM_GATEWAY_DATA_ROOT", "data"), "llm_gateway.db"),
        )


class Rejected(Exception):
    """The request cannot be queued; carries the HTTP status and a message the caller can act on."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class GatewayFailure(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class _Waiter:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    count: int = 0


class Gateway:
    def __init__(self, config: GatewayConfig | None = None, *, http: httpx.AsyncClient | None = None,
                 store: QueueStore | None = None) -> None:
        self.cfg = config or GatewayConfig.from_env()
        self.store = store or QueueStore(self.cfg.db_path)
        self._http = http or httpx.AsyncClient()
        self._waiters: dict[str, _Waiter] = {}
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._running_calls: dict[str, asyncio.Task] = {}
        self._stop = False
        self._timeout_streak = 0    # upstream timeouts in a row; any answer resets it
        self.counters = {"max_tokens_defaulted": 0, "shared_with_identical": 0, "cancelled_by_caller": 0}

    # ---- lifecycle -----------------------------------------------------------------------------------------------

    def start(self, worker_count: int = 1) -> None:
        for i in range(worker_count):
            self._tasks.append(asyncio.create_task(self._worker(f"worker-{i}")))
        self._tasks.append(asyncio.create_task(self._housekeeper()))

    async def stop(self) -> None:
        self._stop = True
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutting down
                pass
        await self._http.aclose()
        self.store.close()

    # ---- the caller's side ---------------------------------------------------------------------------------------

    def build_row(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        if body.get("stream"):
            raise Rejected(400, "stream=true is not supported by the gateway; send a normal (non-streaming) request")
        if not isinstance(body.get("messages"), list) or not body.get("model"):
            raise Rejected(400, "request needs `model` and a `messages` list")
        h = {k.lower(): v for k, v in headers.items()}
        caller = h.get("x-vinu-caller", "").strip() or "unknown"
        try:
            purpose, priority = resolve_purpose(caller, h.get("x-vinu-purpose"))
        except UnknownPurpose as exc:
            raise Rejected(400, str(exc)) from exc
        request = dict(body)
        max_tokens = request.get("max_tokens") or request.get("max_completion_tokens")
        if not max_tokens:
            # Every call must carry an output cap (an unbounded answer once held the only slot for minutes).
            # Fill it in, but loudly: a caller that omits it is a bug to fix, not to hide.
            max_tokens = self.cfg.default_max_tokens
            request["max_tokens"] = max_tokens
            self.counters["max_tokens_defaulted"] += 1
            LOG.warning("caller %s sent no max_tokens; capped at %s", caller, max_tokens)
        now = time.time()
        extra = {k: request[k] for k in ("chat_template_kwargs",) if k in request}
        return {
            "provider": self.cfg.provider, "base_url": self.cfg.upstream_url, "model": str(body["model"]),
            "max_tokens": int(max_tokens), "temperature": request.get("temperature"),
            "extra_json": json.dumps(extra) if extra else None,
            "request_json": json.dumps(request), "tools_json": json.dumps(request["tools"]) if request.get("tools") else None,
            "api_key_ref": self.cfg.api_key_ref or None, "priority": priority, "caller": caller, "purpose": purpose,
            "ticker": h.get("x-vinu-ticker") or None, "run_id": h.get("x-vinu-run-id") or None,
            "deadline_at": now + self.cfg.deadline_sec, "timeout_sec": self.cfg.attempt_timeout_sec,
            "max_attempts": self.cfg.max_attempts,
            "dedupe_key": None if request.get("tools") else dedupe_key(str(body["model"]), request),
        }

    async def submit(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Queue the call and wait for its reply. Returns the upstream's JSON body, unchanged."""
        row = self.build_row(body, headers)
        row_id, shared = self.store.enqueue(row)
        if shared:
            self.counters["shared_with_identical"] += 1
        waiter = self._waiters.setdefault(row_id, _Waiter())
        waiter.count += 1
        self._wake.set()
        try:
            await waiter.event.wait()
            return self._collect(row_id)
        except asyncio.CancelledError:
            self.counters["cancelled_by_caller"] += 1
            raise
        finally:
            waiter.count -= 1
            if waiter.count <= 0:
                self._waiters.pop(row_id, None)
                self._finish_row(row_id)

    def _collect(self, row_id: str) -> dict[str, Any]:
        row = self.store.get(row_id)
        if row is None:  # already archived by the sweep (expired / undelivered)
            raise GatewayFailure(504, "the call expired in the queue before it could run")
        if row["status"] == "done" and row["response_json"]:
            return json.loads(row["response_json"])
        raise GatewayFailure(502, row["error"] or f"call ended as {row['status']}")

    def _finish_row(self, row_id: str) -> None:
        """The last waiter is gone: file the row. Delivered if it has an answer, otherwise by how it ended."""
        row = self.store.get(row_id)
        if row is None:
            return
        status = row["status"]
        if status == "done":
            self.store.archive(row_id, "delivered")
        elif status == "failed":
            self.store.archive(row_id, "failed")
        else:  # queued or running: the caller hung up first
            call = self._running_calls.get(row_id)
            if call is not None:
                call.cancel()
            self.store.archive(row_id, "cancelled")

    def _notify(self, row_id: str) -> None:
        w = self._waiters.get(row_id)
        if w:
            w.event.set()

    async def models(self) -> tuple[int, Any]:
        """Read-only passthrough of the model server's /models: callers (the agent) ask it for the real context size
        to budget their prompts. It is not a generation, so it does not queue."""
        try:
            resp = await self._http.get(self.cfg.upstream_url.rstrip("/") + "/models", timeout=10.0)
            return resp.status_code, resp.json()
        except (httpx.RequestError, ValueError) as exc:
            return 502, {"error": {"message": f"model server unreachable: {type(exc).__name__}: {exc}"}}

    # ---- the worker ----------------------------------------------------------------------------------------------

    async def _worker(self, worker_id: str) -> None:
        while not self._stop:
            row = await asyncio.to_thread(self.store.claim_next, worker_id, age_step_sec=self.cfg.age_step_sec)
            if row is None:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
                continue
            if row["id"] not in self._waiters:  # every caller already hung up
                self.store.archive(row["id"], "cancelled")
                continue
            call = asyncio.create_task(self._call_upstream(row))
            self._running_calls[row["id"]] = call
            try:
                await call
            except asyncio.CancelledError:
                if self._stop:
                    raise
                LOG.info("call %s aborted: caller hung up", row["id"])
            except Exception:  # noqa: BLE001 - a bug here must not kill the worker
                LOG.exception("worker crashed on call %s", row["id"])
                self.store.finish_failed(row["id"], "gateway worker error")
                self._notify(row["id"])
            finally:
                self._running_calls.pop(row["id"], None)

    async def _call_upstream(self, row) -> None:
        rid = row["id"]
        headers = {"Content-Type": "application/json"}
        if row["api_key_ref"]:
            key = load_secret(row["api_key_ref"])
            if not key:
                self.store.finish_failed(rid, f"secret {row['api_key_ref']!r} is missing or empty")
                self._notify(rid)
                return
            headers["Authorization"] = f"Bearer {key}"
        url = row["base_url"].rstrip("/") + "/chat/completions"
        error, transient = "", True
        try:
            resp = await self._http.post(url, headers=headers, content=row["request_json"], timeout=row["timeout_sec"])
            self._timeout_streak = 0
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage") or {}
                self.store.finish_ok(rid, resp.text, usage.get("prompt_tokens"), usage.get("completion_tokens"))
                self._notify(rid)
                return
            error = f"upstream HTTP {resp.status_code}: {resp.text[:300]}"
            transient = resp.status_code in _TRANSIENT_STATUS
        except httpx.TimeoutException:
            error = f"upstream did not answer within {row['timeout_sec']:.0f}s"
            self._timeout_streak += 1
            if self._timeout_streak > STALL_STREAK:
                # The model server is stalled, not slow (normal calls end well inside the timeout). Retrying would hold the
                # one slot for 3 x the timeout per call while everything behind it expires; fail now so callers can react.
                transient = False
                error += " (the model server is stalled; not retried)"
        except httpx.RequestError as exc:
            error = f"upstream unreachable: {type(exc).__name__}: {exc}"
        except ValueError as exc:
            error, transient = f"upstream sent invalid JSON: {exc}", False
        if transient and row["attempts"] < row["max_attempts"]:
            delay = min(30.0, 2.0 ** row["attempts"])
            LOG.warning("call %s attempt %s/%s failed (%s); retrying in %.0fs", rid, row["attempts"],
                        row["max_attempts"], error, delay)
            self.store.retry_later(rid, error, delay)
            return
        self.store.finish_failed(rid, error)
        self._notify(rid)

    # ---- housekeeping --------------------------------------------------------------------------------------------

    async def _housekeeper(self) -> None:
        last_trim = 0.0
        while not self._stop:
            await asyncio.sleep(self.cfg.sweep_every_sec)
            try:
                moved = await asyncio.to_thread(
                    self.store.sweep, undelivered_after_sec=self.cfg.undelivered_after_sec)
                for rid in moved["expired"] + moved["undelivered"]:
                    self._notify(rid)
                if moved["requeued"]:
                    self._wake.set()
                if time.time() - last_trim > 3600:
                    last_trim = time.time()
                    await asyncio.to_thread(self.store.trim_history, self.cfg.history_json_days)
            except Exception:  # noqa: BLE001
                LOG.exception("queue housekeeping failed")
