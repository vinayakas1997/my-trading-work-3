import asyncio
import json

import httpx
import pytest

from vinu_llm_gateway.gateway import Gateway, GatewayConfig, GatewayFailure, Rejected
from vinu_llm_gateway.priorities import UnknownPurpose, resolve_purpose

REPLY = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}


def _body(text="hello", **kw):
    return {"model": "m", "messages": [{"role": "user", "content": text}], "max_tokens": 50, **kw}


def _hdr(caller="vinu-research", purpose=None):
    h = {"x-vinu-caller": caller}
    if purpose:
        h["x-vinu-purpose"] = purpose
    return h


class Upstream:
    """A fake model server, recording the order it was asked in."""

    def __init__(self, delay=0.0, fail_first=0, status=500):
        self.served, self.delay, self.fail_first, self.status = [], delay, fail_first, status
        self.auth_headers = []
        self.gate = None

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth_headers.append(request.headers.get("authorization"))
        body = json.loads(request.content)
        self.served.append(body["messages"][0]["content"])
        if self.gate is not None:
            await self.gate.wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_first > 0:
            self.fail_first -= 1
            return httpx.Response(self.status, text="busy")
        return httpx.Response(200, json=REPLY)


def _gw(tmp_path, upstream, **cfg):
    config = GatewayConfig(db_path=str(tmp_path / "g.db"), upstream_url="http://up/v1", **cfg)
    return Gateway(config, http=httpx.AsyncClient(transport=httpx.MockTransport(upstream)))


async def test_reply_is_the_upstream_reply_unchanged(tmp_path):
    gw = _gw(tmp_path, Upstream())
    gw.start()
    try:
        assert await gw.submit(_body(), _hdr()) == REPLY
        h = gw.store.history()
        assert h[0]["archive_reason"] == "delivered" and h[0]["prompt_tokens"] == 3 and h[0]["purpose"] == "research"
        assert gw.store.stats()["queue"] == {}
    finally:
        await gw.stop()


async def test_urgent_call_jumps_a_backlog_but_waits_for_the_one_running(tmp_path):
    up = Upstream()
    up.gate = asyncio.Event()
    gw = _gw(tmp_path, up)
    gw.start()
    try:
        first = asyncio.create_task(gw.submit(_body("first"), _hdr(purpose="hindsight")))
        await asyncio.sleep(0.3)                                    # `first` is running, held at the gate
        backlog = [asyncio.create_task(gw.submit(_body(f"bg{i}"), _hdr(purpose="hindsight"))) for i in range(3)]
        await asyncio.sleep(0.1)
        urgent = asyncio.create_task(gw.submit(_body("urgent"), _hdr(caller="vinu-live", purpose="live_decision")))
        await asyncio.sleep(0.1)
        up.gate.set()
        await asyncio.wait_for(asyncio.gather(first, urgent, *backlog), 15)
        assert up.served[0] == "first" and up.served[1] == "urgent"
    finally:
        await gw.stop()


async def test_transient_failure_is_retried_then_succeeds(tmp_path):
    up = Upstream(fail_first=1)
    gw = _gw(tmp_path, up)
    gw.start()
    try:
        assert await asyncio.wait_for(gw.submit(_body(), _hdr()), 15) == REPLY
        assert gw.store.history()[0]["attempts"] == 2
    finally:
        await gw.stop()


class _Silent:
    """A model server that takes the request and never answers (the stall seen in production, 2026-10-07 10:21 to 11:37)."""

    def __init__(self):
        self.asked = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked += 1
        raise httpx.ReadTimeout("no answer", request=request)


async def test_a_stalled_model_server_is_not_retried_so_it_cannot_hold_the_slot(tmp_path):
    """Each call used to try three times at 300 s: 15 minutes of the one slot per call while the queue behind it expired."""
    from vinu_llm_gateway.gateway import STALL_STREAK

    silent = _Silent()
    gw = _gw(tmp_path, silent)
    gw._timeout_streak = STALL_STREAK                  # the server has already timed out STALL_STREAK times in a row
    gw.start()
    try:
        with pytest.raises(GatewayFailure) as e:
            await asyncio.wait_for(gw.submit(_body(), _hdr()), 15)
        assert silent.asked == 1 and "stalled" in e.value.message
    finally:
        await gw.stop()


async def test_an_answer_clears_the_timeout_streak(tmp_path):
    up = Upstream()
    gw = _gw(tmp_path, up)
    gw._timeout_streak = 1
    gw.start()
    try:
        assert await asyncio.wait_for(gw.submit(_body(), _hdr()), 15) == REPLY
        assert gw._timeout_streak == 0
    finally:
        await gw.stop()


async def test_permanent_failure_is_reported_not_retried(tmp_path):
    up = Upstream(fail_first=99, status=400)
    gw = _gw(tmp_path, up)
    gw.start()
    try:
        with pytest.raises(GatewayFailure) as e:
            await asyncio.wait_for(gw.submit(_body(), _hdr()), 15)
        assert "400" in e.value.message and len(up.served) == 1
        assert gw.store.history()[0]["archive_reason"] == "failed"
    finally:
        await gw.stop()


async def test_caller_hanging_up_frees_the_slot(tmp_path):
    up = Upstream()
    up.gate = asyncio.Event()                      # the first call never finishes on its own
    gw = _gw(tmp_path, up)
    gw.start()
    try:
        stuck = asyncio.create_task(gw.submit(_body("stuck"), _hdr()))
        await asyncio.sleep(0.3)
        stuck.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stuck
        up.gate.set()
        assert await asyncio.wait_for(gw.submit(_body("next"), _hdr()), 15) == REPLY
        assert "cancelled" in {h["archive_reason"] for h in gw.store.history()}
        assert gw.counters["cancelled_by_caller"] == 1
    finally:
        await gw.stop()


async def test_identical_calls_in_flight_share_one_run(tmp_path):
    up = Upstream(delay=0.3)
    gw = _gw(tmp_path, up)
    gw.start()
    try:
        a, b = await asyncio.wait_for(
            asyncio.gather(gw.submit(_body("same"), _hdr()), gw.submit(_body("same"), _hdr())), 15)
        assert a == b == REPLY and up.served == ["same"]
    finally:
        await gw.stop()


def test_request_without_max_tokens_gets_the_default_and_is_counted(tmp_path):
    gw = _gw(tmp_path, Upstream(), default_max_tokens=777)
    body = _body()
    del body["max_tokens"]
    row = gw.build_row(body, _hdr())
    assert row["max_tokens"] == 777 and json.loads(row["request_json"])["max_tokens"] == 777
    assert gw.counters["max_tokens_defaulted"] == 1


def test_bad_requests_are_rejected_with_a_reason(tmp_path):
    gw = _gw(tmp_path, Upstream())
    with pytest.raises(Rejected, match="unknown purpose"):
        gw.build_row(_body(), _hdr(purpose="make_me_urgent"))
    with pytest.raises(Rejected, match="no default purpose"):
        gw.build_row(_body(), _hdr(caller="mystery"))
    with pytest.raises(Rejected, match="stream"):
        gw.build_row(_body(stream=True), _hdr())
    with pytest.raises(Rejected, match="messages"):
        gw.build_row({"model": "m"}, _hdr())


def test_purpose_table_is_consistent():
    assert resolve_purpose("vinu-live", None) == ("live_decision", 1)
    assert resolve_purpose("x", "hindsight") == ("hindsight", 5)
    with pytest.raises(UnknownPurpose):
        resolve_purpose("x", None)


async def test_api_key_is_read_from_its_secret_file_and_never_stored(tmp_path, monkeypatch):
    (tmp_path / "up_key").write_text("SUPER-SECRET-VALUE\n")
    monkeypatch.setenv("VINU_SECRETS_DIR", str(tmp_path))
    up = Upstream()
    gw = _gw(tmp_path, up, api_key_ref="up_key")
    gw.start()
    try:
        await gw.submit(_body(), _hdr())
        assert up.auth_headers == ["Bearer SUPER-SECRET-VALUE"]
        dump = json.dumps([dict(r) for r in gw.store._conn.execute("select * from llm_history")])
        assert "SUPER-SECRET-VALUE" not in dump and "up_key" in dump       # the NAME is stored, the value never
    finally:
        await gw.stop()


async def test_missing_secret_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_SECRETS_DIR", str(tmp_path))
    gw = _gw(tmp_path, Upstream(), api_key_ref="nope")
    gw.start()
    try:
        with pytest.raises(GatewayFailure, match="missing or empty"):
            await asyncio.wait_for(gw.submit(_body(), _hdr()), 15)
    finally:
        await gw.stop()
