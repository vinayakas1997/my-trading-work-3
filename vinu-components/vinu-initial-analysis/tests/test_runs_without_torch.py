"""initial-analysis must import, build its app and discover every angle with torch UNAVAILABLE (it no longer ships it; the
model angles run in the model service). Run in a subprocess that blocks torch, so it is meaningful even where torch is installed."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[1]

BLOCK = '''import sys, importlib.abc
BLOCKED = ('torch', 'transformers', 'chronos', 'timesfm')
class _Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in BLOCKED:
            raise ModuleNotFoundError("No module named '" + name + "' (blocked by the test)")
sys.meta_path.insert(0, _Block())
'''


def _run(code: str, tmp_path: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, "VINU_INITIAL_ANALYSIS_DATA_ROOT": str(tmp_path), "VINU_EDGE_DATA_ROOT": str(tmp_path / "e")}
    env.update(extra_env or {})
    (tmp_path / "e").mkdir(exist_ok=True)
    return subprocess.run([sys.executable, "-c", BLOCK + textwrap.dedent(code)], cwd=SERVICE_DIR, env=env,
                          capture_output=True, text=True, timeout=240)


def test_the_app_builds_and_every_angle_is_discovered_without_torch(tmp_path):
    p = _run("""
        from vinu_initial_analysis.server.app import create_app
        from vinu_initial_analysis.runner import AngleRunner
        app = create_app()
        loaded = [m for m in ('torch','transformers','chronos','timesfm') if m in sys.modules]
        assert not loaded, loaded
        print('OK')
    """, tmp_path)
    assert p.returncode == 0 and "OK" in p.stdout, p.stdout[-800:] + p.stderr[-1500:]


def test_the_factsheet_summary_does_not_need_the_torch_registry(tmp_path):
    p = _run("""
        from pathlib import Path
        from vinu_initial_analysis.storage.factsheet import write_summary
        from vinu_initial_analysis.storage.meta import RunLog
        from vinu_initial_analysis.storage.parquet import AngleStorage
        root = Path(sys.argv[0] if False else '.')
        import tempfile
        d = Path(tempfile.mkdtemp())
        out = write_summary(d, 'AAPL', RunLog(d / 'runs.db'), AngleStorage(str(d)))
        text = out.read_text(encoding='utf-8')
        assert 'chronos' in text and 'arima' in text
        print('OK')
    """, tmp_path)
    assert p.returncode == 0 and "OK" in p.stdout, p.stdout[-800:] + p.stderr[-1500:]


def test_a_model_angle_run_goes_to_the_service_and_never_touches_torch(tmp_path):
    p = _run("""
        import pandas as pd
        from pathlib import Path
        import tempfile
        from vinu_infra import model_client
        from vinu_initial_analysis.runner import AngleRunner
        from vinu_initial_analysis.storage.meta import RunLog
        from vinu_initial_analysis.storage.parquet import AngleStorage

        class Price:
            def get_candles(self, *a, **k):
                return [{'bar_ts': i, 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1} for i in range(600)]

        got = []
        model_client.compute_angle = lambda angle, **kw: got.append(angle) or pd.DataFrame([{'symbol': kw['symbol'], 'status': 'ok'}])
        d = Path(tempfile.mkdtemp())
        r = AngleRunner(AngleStorage(str(d)), RunLog(d / 'runs.db'), price_client=Price())
        out = r.run('AAPL', angle_names=['chronos', 'kronos'], time_format='1D')
        assert got == ['chronos', 'kronos'], (got, out)
        assert all(v['status'] == 'completed' for v in out.values()), out
        assert 'torch' not in sys.modules
        print('OK')
    """, tmp_path, {"VINU_MODEL_SERVICE_URL": "http://models-api:8096", "VINU_MODELS_ENABLED": "true"})
    assert p.returncode == 0 and "OK" in p.stdout, p.stdout[-800:] + p.stderr[-1500:]
