"""Stage A (A37): hash-chained tamper-evident safety ledger."""

from __future__ import annotations

import json

import pytest

from vinu_agent.broker.audit_ledger import GENESIS_HASH, HashChainedLedger


@pytest.fixture
def ledger(tmp_path):
    return HashChainedLedger(tmp_path / "ledger.jsonl")


class TestAppendAndChain:
    def test_first_entry_links_to_genesis(self, ledger) -> None:
        e = ledger.append("halt", {"scope": "global"})
        assert e["seq"] == 0
        assert e["prev_hash"] == GENESIS_HASH
        assert len(e["hash"]) == 64

    def test_each_entry_links_to_the_previous_hash(self, ledger) -> None:
        a = ledger.append("halt", {"scope": "global"})
        b = ledger.append("resume", {"scope": "global"})
        c = ledger.append("halt", {"scope": "AAPL"})
        assert b["prev_hash"] == a["hash"]
        assert c["prev_hash"] == b["hash"]
        assert [a["seq"], b["seq"], c["seq"]] == [0, 1, 2]

    def test_verify_passes_on_an_untouched_ledger(self, ledger) -> None:
        for i in range(5):
            ledger.append("halt" if i % 2 == 0 else "resume", {"scope": "global"})
        v = ledger.verify()
        assert v.ok is True
        assert v.entries == 5
        assert v.broken_at is None

    def test_append_is_durable_across_a_fresh_reader(self, ledger, tmp_path) -> None:
        ledger.append("halt", {"scope": "global"})
        ledger.append("resume", {"scope": "global"})
        reopened = HashChainedLedger(tmp_path / "ledger.jsonl")
        assert len(reopened.entries()) == 2
        assert reopened.verify().ok is True
        # a further append continues the chain, not restarts it
        e = reopened.append("halt", {"scope": "MSFT"})
        assert e["seq"] == 2
        assert reopened.verify().ok is True


class TestTamperDetection:
    def _rows(self, ledger):
        return [json.loads(l) for l in ledger.path.read_text().splitlines() if l.strip()]

    def _write(self, ledger, rows):
        ledger.path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def test_edited_payload_is_detected(self, ledger) -> None:
        ledger.append("halt", {"scope": "global"})
        ledger.append("resume", {"scope": "global"})
        rows = self._rows(ledger)
        rows[0]["payload"] = {"scope": "AAPL"}   # someone rewrites history
        self._write(ledger, rows)

        v = ledger.verify()
        assert v.ok is False
        assert v.broken_at == 0
        assert "altered" in v.reason

    def test_deleted_middle_entry_is_detected(self, ledger) -> None:
        for _ in range(4):
            ledger.append("halt", {"scope": "global"})
        rows = self._rows(ledger)
        del rows[2]                                # drop one record
        self._write(ledger, rows)

        v = ledger.verify()
        assert v.ok is False
        assert v.broken_at == 2  # seq no longer matches its position

    def test_reordered_entries_are_detected(self, ledger) -> None:
        ledger.append("halt", {"scope": "a"})
        ledger.append("resume", {"scope": "b"})
        ledger.append("halt", {"scope": "c"})
        rows = self._rows(ledger)
        rows[1], rows[2] = rows[2], rows[1]
        self._write(ledger, rows)

        assert ledger.verify().ok is False

    def test_appended_forged_entry_without_the_chain_is_detected(self, ledger) -> None:
        ledger.append("halt", {"scope": "global"})
        rows = self._rows(ledger)
        rows.append({
            "seq": 1, "ts": "2026-01-01T00:00:00+00:00", "event_type": "resume",
            "payload": {"scope": "global"}, "prev_hash": "deadbeef" * 8, "hash": "f00d" * 16,
        })
        self._write(ledger, rows)

        v = ledger.verify()
        assert v.ok is False
        assert v.broken_at == 1


class TestBestEffort:
    def test_append_never_raises_on_a_bad_path(self, tmp_path) -> None:
        # point the ledger at a path whose parent is a file, not a dir
        blocker = tmp_path / "blocker"
        blocker.write_text("x")
        bad = HashChainedLedger(blocker / "nested" / "ledger.jsonl")
        e = bad.append("halt", {"scope": "global"})
        assert e["seq"] == -1  # signalled failure, but did not raise
