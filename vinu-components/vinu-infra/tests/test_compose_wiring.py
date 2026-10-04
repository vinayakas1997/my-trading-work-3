"""Deployment wiring that no unit test can see: a file a service reads at a fixed path must actually be mounted there
(features-logic-checking F5)."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _volumes(service: str) -> list[str]:
    doc = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return [str(v) for v in doc["services"][service].get("volumes", [])]


def test_portfolio_api_mounts_the_strategy_tags_it_reads():
    """The regime-alignment tilt and the sleeve split read <app root>/vinu-agent/skills/strategy-tags/tags.yaml
    (PortfolioConfig default, resolved from the package location: /app inside the image). Before this mount the file
    did not exist in the container, tags loaded as empty, and the regime tilt was a permanent no-op."""
    assert any(v.endswith(":/app/vinu-agent/skills:ro") for v in _volumes("portfolio-api"))


def test_the_default_tags_path_lands_inside_that_mount():
    """/app/vinu-portfolio/vinu_portfolio/config.py -> parents[2] is /app, so the default is
    /app/vinu-agent/skills/strategy-tags/tags.yaml, which the mount above covers."""
    from pathlib import PurePosixPath

    package_file = PurePosixPath("/app/vinu-portfolio/vinu_portfolio/config.py")
    tags = package_file.parents[2] / "vinu-agent" / "skills" / "strategy-tags" / "tags.yaml"
    assert str(tags).startswith("/app/vinu-agent/skills/")
    assert (COMPOSE.parent / "vinu-agent" / "skills" / "strategy-tags" / "tags.yaml").is_file()


@pytest.mark.parametrize("service", ["research-api", "agent-api"])
def test_services_that_assess_maturity_can_read_the_live_decision_database(service):
    """D3: the maturity tier counts closed live-decision trades, read from live-api's data through a read-only mount
    at /live-data, and the env var points the assessor at that mount."""
    assert any(v.endswith(":/live-data:ro") and v.startswith("./data/live") for v in _volumes(service))
    doc = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert doc["services"][service]["environment"]["VINU_RESEARCH_LIVE_DATA_ROOT"] == "/live-data"
