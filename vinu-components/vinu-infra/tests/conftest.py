"""Every infra test runs from its own empty folder. Some code defaults its data root to `./data` under the working folder when
no environment variable is set, so a host run from `vinu-components/` used to leave `strategy_store.db` and
`market_regime_history.db` next to the real stores, where they look like real data (problem log O18)."""

import pytest


@pytest.fixture(autouse=True)
def _run_in_an_empty_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
