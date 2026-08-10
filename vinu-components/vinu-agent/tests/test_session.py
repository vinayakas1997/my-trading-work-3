import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from vinu_agent.session.store import SessionStore
from vinu_agent.session.models import Session, Message, Attempt
from vinu_agent.session.events import EventBus, SSEEvent


class TestSessionStore:
    @pytest.fixture
    def store(self) -> SessionStore:
        tmp = Path(tempfile.mkdtemp())
        return SessionStore(tmp)

    def test_create_and_get_session(self, store: SessionStore) -> None:
        s = Session(title="test")
        saved = store.create_session(s)
        assert saved.session_id == s.session_id
        loaded = store.get_session(s.session_id)
        assert loaded is not None
        assert loaded.title == "test"

    def test_get_session_not_found(self, store: SessionStore) -> None:
        assert store.get_session("nonexistent") is None

    def test_update_session(self, store: SessionStore) -> None:
        s = Session(title="original")
        store.create_session(s)
        s.title = "updated"
        store.update_session(s)
        loaded = store.get_session(s.session_id)
        assert loaded is not None
        assert loaded.title == "updated"

    def test_list_sessions(self, store: SessionStore) -> None:
        s1 = Session(title="a")
        s2 = Session(title="b")
        store.create_session(s1)
        store.create_session(s2)
        sessions = store.list_sessions()
        assert len(sessions) >= 2

    def test_delete_session(self, store: SessionStore) -> None:
        s = Session(title="delete me")
        store.create_session(s)
        assert store.delete_session(s.session_id) is True
        assert store.delete_session("nope") is False
        assert store.get_session(s.session_id) is None

    def test_append_and_get_messages(self, store: SessionStore) -> None:
        s = Session(title="msg test")
        store.create_session(s)
        msg = Message(session_id=s.session_id, role="user", content="hello")
        store.append_message(s.session_id, msg)
        msgs = store.get_messages(s.session_id)
        assert len(msgs) == 1
        assert msgs[0].content == "hello"

    def test_get_messages_empty(self, store: SessionStore) -> None:
        assert store.get_messages("nope") == []

    def test_get_messages_limit(self, store: SessionStore) -> None:
        s = Session(title="limit")
        store.create_session(s)
        for i in range(10):
            store.append_message(s.session_id, Message(session_id=s.session_id, content=str(i)))
        msgs = store.get_messages(s.session_id, limit=5)
        assert len(msgs) <= 5

    def test_save_and_get_attempt(self, store: SessionStore) -> None:
        s = Session(title="attempt test")
        store.create_session(s)
        a = Attempt(session_id=s.session_id, prompt="test prompt")
        store.save_attempt(s.session_id, a)
        loaded = store.get_attempt(s.session_id, a.attempt_id)
        assert loaded.prompt == "test prompt"
        assert loaded.status.value == "pending"


class TestEventBus:
    @pytest.fixture
    def bus(self) -> EventBus:
        return EventBus(max_buffer_size=10)

    def test_publish_and_subscribe(self, bus: EventBus) -> None:
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)
        received = []

        async def sub():
            async for event in bus.subscribe("s1"):
                received.append(event)
                break

        async def pub():
            bus.publish(SSEEvent(event_type="test", data={"key": "val"}, session_id="s1"))

        async def run():
            await asyncio.gather(sub(), pub())

        loop.run_until_complete(run())
        loop.close()
        assert len(received) == 1
        assert received[0].event_type == "test"

    def test_replay_from_event_id(self, bus: EventBus) -> None:
        e1 = SSEEvent(event_type="e1", session_id="s2", event_id="ev1")
        e2 = SSEEvent(event_type="e2", session_id="s2", event_id="ev2")
        e3 = SSEEvent(event_type="e3", session_id="s2", event_id="ev3")
        bus.publish(e1)
        bus.publish(e2)
        bus.publish(e3)

        replayed = bus._replay("s2", "ev1")
        assert len(replayed) == 2
        assert replayed[0].event_type == "e2"
        assert replayed[1].event_type == "e3"

    def test_replay_no_match(self, bus: EventBus) -> None:
        e1 = SSEEvent(event_type="e1", session_id="s3")
        bus.publish(e1)
        replayed = bus._replay("s3", "nonexistent")
        assert len(replayed) == 0

    def test_buffer_size_limit(self, bus: EventBus) -> None:
        for i in range(15):
            bus.publish(SSEEvent(event_type=str(i), session_id="buf"))
        assert len(bus._buffer) == 10

    def test_heartbeat_on_timeout(self) -> None:
        bus = EventBus(queue_timeout=0.1)
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)
        received = []

        async def sub():
            async for event in bus.subscribe("heartbeat-session"):
                received.append(event)
                if event.event_type == "heartbeat":
                    break

        loop.run_until_complete(sub())
        loop.close()
        assert len(received) >= 1
        assert received[-1].event_type == "heartbeat"

    def test_sse_format(self) -> None:
        event = SSEEvent(event_id="abc123", event_type="test", data={"x": 1}, session_id="s1")
        sse = event.to_sse()
        assert "id: abc123" in sse
        assert "event: test" in sse
        assert '"x": 1' in sse

    def test_subscriber_removed_on_finally(self) -> None:
        bus = EventBus(queue_timeout=0.1)
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)

        async def run():
            gen = bus.subscribe("cleanup")
            try:
                async for _ in gen:
                    break
            finally:
                await gen.aclose()

        loop.run_until_complete(run())
        loop.close()
        assert "cleanup" not in bus._subscribers


class TestSessionService:
    @pytest.fixture
    def service(self):
        tmp = Path(tempfile.mkdtemp())
        store = SessionStore(tmp)
        bus = EventBus()
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)
        from vinu_agent.session.service import SessionService
        svc = SessionService(store=store, event_bus=bus)
        yield svc
        loop.close()

    def test_create_session(self, service) -> None:
        loop = asyncio.new_event_loop()
        s = loop.run_until_complete(service.create_session(title="svc test"))
        loop.close()
        assert s.title == "svc test"
        assert s.session_id is not None

    def test_send_message_nonexistent_session(self, service) -> None:
        import pytest
        loop = asyncio.new_event_loop()
        with pytest.raises(ValueError, match="not found"):
            loop.run_until_complete(service.send_message("nope", "hello"))
        loop.close()

    def test_send_message_non_user_returns_early(self, service) -> None:
        loop = asyncio.new_event_loop()
        s = loop.run_until_complete(service.create_session())
        result = loop.run_until_complete(
            service.send_message(s.session_id, "assistant reply", role="assistant")
        )
        loop.close()
        assert "attempt_id" not in result

    def test_init_sets_active_loops_and_context_builder(self, service) -> None:
        """Regression test: a botched edit once left `self._active_loops =
        {}` / `self._context_builder = None` as dead code stranded after a
        `return` inside a different (static) method, so __init__ silently
        never set them at all -- any real user message would have crashed
        with AttributeError the first time `_run_with_agent` touched
        `self._active_loops[session_id] = ...`. No existing test actually
        drives a real user message through `_run_with_agent` (both other
        tests in this class either hit a nonexistent session or use
        role="assistant", which returns before ever reaching it), so this
        checks the attributes directly instead."""
        assert service._active_loops == {}
        assert service._context_builder is None

    def test_cancel_current_on_fresh_service_is_false_not_a_crash(self, service) -> None:
        assert service.cancel_current("some-session-id") is False
