"""v2 audit S2: the poller asks for closed bars only when `live_decision_closed_bars_only` is on."""

import asyncio

from vinu_live.live_decision.bars_client import fetch_recent_bars


class _Http:
    def __init__(self):
        self.params = None

    async def get(self, url, params=None):
        self.params = params

        class R:
            status_code = 200

            def json(self):
                return {"data": [{"bar_ts": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]}
        return R()


def test_closed_only_is_sent_only_when_asked():
    h = _Http()
    asyncio.run(fetch_recent_bars(h, "http://x", "AAPL", "1d", 2))
    assert "closed_only" not in h.params
    asyncio.run(fetch_recent_bars(h, "http://x", "AAPL", "1d", 2, closed_only=True))
    assert h.params["closed_only"] is True and h.params["limit"] == 2


def test_the_config_flag_defaults_off_and_reads_the_env(monkeypatch):
    from vinu_live.config import LiveConfig
    assert LiveConfig().live_decision_closed_bars_only is False
    monkeypatch.setenv("VINU_LIVE_DECISION_CLOSED_BARS_ONLY", "true")
    assert LiveConfig.from_env().live_decision_closed_bars_only is True
