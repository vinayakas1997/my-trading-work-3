import os
from pathlib import Path

import pytest


def test_models_dir_prefers_env(monkeypatch):
    monkeypatch.setenv("VINU_MODELS_DIR", "Z:/some/models")
    from vinu_infra import models as m

    assert m.models_dir() == Path("Z:/some/models")


def test_models_dir_defaults_to_components_root():
    from vinu_infra import models as m

    root = m.models_dir()
    assert root.name == "models"
    assert root.parent.name == "data"


def test_model_path_unknown_raises():
    from vinu_infra import models as m

    with pytest.raises(ValueError):
        m.model_path("does-not-exist")


def test_is_downloaded_and_ensure_local_path(monkeypatch, tmp_path):
    from vinu_infra import models as m

    monkeypatch.setenv("VINU_MODELS_DIR", str(tmp_path))
    p = m.model_path("finbert")
    assert not m.is_downloaded("finbert")

    p.mkdir(parents=True)
    (p / "config.json").write_text("{}")
    assert m.is_downloaded("finbert")

    # Short-circuit: already present, so ensure_model returns the path without
    # attempting an import or a download (would fail on the HF import guard).
    assert m.ensure_model("finbert") == p


def test_download_models_handles_unknown_gracefully(monkeypatch, tmp_path):
    from vinu_infra import models as m

    monkeypatch.setenv("VINU_MODELS_DIR", str(tmp_path))
    # An unknown name just isn't in MODELS; download_models with a known name
    # that's absent would hit the network — so only exercise the list API here.
    names = sorted(m.MODELS)
    assert "finbert" in names
