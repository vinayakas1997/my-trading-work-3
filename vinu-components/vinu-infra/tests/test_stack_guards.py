"""Guards for deployment mistakes that were made once and must not come back (each one was found by running Docker):

* the models container is dormant: behind a compose profile, never built or started by default
* every image installs every vinu package its code imports when it loads (stock-api lacked vinu-tools; quant-core,
  research and agent lacked vinu-portfolio)
* API keys live only in secrets/ files, never as values in .env or .env-example; the broker is pinned to paper
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]          # vinu-components/
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

PACKAGES = {
    "vinu_tools": "vinu-tools", "vinu_infra": "vinu-infra", "vinu_stock": "vinu-stock-price",
    "vinu_research": "vinu-research", "vinu_agent": "vinu-agent", "vinu_live": "vinu-live",
    "vinu_portfolio": "vinu-portfolio", "vinu_strategy": "vinu-strategy", "vinu_simulator": "vinu-simulator",
    "vinu_news": "vinu-news", "vinu_initial_analysis": "vinu-initial-analysis", "vinu_screener": "vinu-screener",
    "vinu_reflection": "vinu-reflection", "vinu_models": "vinu-models",
}

# module-level imports that are known to be unused at startup in that image, each with the reason
_LOCAL_PRICE = "clients/local_price_client.py is only imported in the in-process price mode; the container reads prices over HTTP"
ALLOWED_MISSING = {
    ("initial-analysis-api", "vinu-stock-price"): _LOCAL_PRICE,
    ("models-api", "vinu-stock-price"): _LOCAL_PRICE + " (dormant image, copies the analysis code)",
    ("quant-core-api", "vinu-research"):
        "vinu-portfolio is installed --no-deps for circuit_breakers only; research_link.py is never imported there",
}


# ------------------------------------------------------------------------------------ models container is dormant

def test_models_api_is_behind_a_profile_so_it_is_never_built_or_started_by_default():
    assert COMPOSE["services"]["models-api"].get("profiles") == ["models"]


def test_no_default_service_depends_on_models_api():
    for name, svc in COMPOSE["services"].items():
        deps = svc.get("depends_on") or {}
        deps = list(deps) if isinstance(deps, (dict, list)) else []
        assert "models-api" not in deps, f"{name} would force the dormant models container to start"


# --------------------------------------------------------------------------- images contain what the code imports

def _module_level_imports(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {m.group(2) for m in re.finditer(r"^(from|import)\s+(vinu_[a-z_]+)", text, re.M)}   # column 0 = hard import


def _missing_per_service() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for svc, spec in COMPOSE["services"].items():
        build = spec.get("build")
        if not build:
            continue
        dockerfile = ROOT / build["dockerfile"]
        copied = set(re.findall(r"COPY\s+(vinu-[a-z-]+)/?\s", dockerfile.read_text(encoding="utf-8")))
        copied.add(Path(build["dockerfile"]).parts[0])
        for folder in sorted(copied):
            for f in (ROOT / folder).rglob("*.py"):
                if {"tests", ".venv", "node_modules", "__pycache__", "scripts", "docs"} & set(f.parts):
                    continue
                for module in _module_level_imports(f):
                    pkg = PACKAGES.get(module)
                    if pkg and pkg not in copied:
                        out.setdefault(svc, {}).setdefault(pkg, f"{folder}/{f.relative_to(ROOT / folder)}")
    return out


def test_every_image_installs_every_vinu_package_its_code_imports_at_load():
    problems = []
    for svc, missing in _missing_per_service().items():
        for pkg, example in missing.items():
            if (svc, pkg) not in ALLOWED_MISSING:
                problems.append(f"{svc}: image does not install {pkg} (imported by {example})")
    assert not problems, "\n".join(problems)


def test_the_allowlist_has_no_stale_entries():
    found = {(svc, pkg) for svc, missing in _missing_per_service().items() for pkg in missing}
    assert set(ALLOWED_MISSING) <= found, "an allowed missing import is no longer missing: remove it from the list"


# -------------------------------------------------------------------------------------- secrets and the paper broker

SECRET_NAMES = {"VINU_API_KEY", "ALPACA_API_KEY", "ALPACA_API_SECRET", "VINU_LLM_API_KEY", "POLYGON_API_KEY",
                "FMP_API_KEY"}


@pytest.mark.parametrize("name", [".env-example", ".env"])
def test_secret_values_are_never_written_in_env_files(name):
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} not present")
    leaks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z_]+)=(.+)$", line)
        if m and m.group(1) in SECRET_NAMES and m.group(2).strip():
            leaks.append(m.group(1))
    assert not leaks, f"{name} holds values for {leaks}: keys belong in secrets/ files only"


def test_env_example_pins_the_broker_to_paper():
    assert re.search(r"^ALPACA_PAPER=true\s*$", (ROOT / ".env-example").read_text(encoding="utf-8"), re.M)


def test_env_example_carries_the_real_system_flag_profile():
    text = (ROOT / ".env-example").read_text(encoding="utf-8")
    for flag in ("VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION", "VINU_LIVE_SCHEDULER_ENTRY_GUARDS_ENABLED",
                 "VINU_LIVE_PRECONDITION_ENFORCING_ENABLED", "VINU_PORTFOLIO_MATURITY_CAPITAL_GATING_ENABLED"):
        assert re.search(rf"^{flag}=true\s*$", text, re.M), f"{flag} should be on in the example profile"


# ----------------------------------------------------------------------------- shipped strategies reach the service

def test_quant_core_seeds_the_strategy_volume_from_the_image():
    """The strategy service reads $VINU_STRATEGY_STRATEGIES_DIR (an empty mounted volume on a fresh machine) while the
    shipped YAML strategies live in the image; without seeding, GET /strategy/strategies is [] and nothing can run."""
    dockerfile = (ROOT / "vinu-quant-core" / "Dockerfile").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["/app/entrypoint.sh"]' in dockerfile
    script = (ROOT / "vinu-quant-core" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "cp -n /app/vinu-strategy/strategies/*.yaml" in script          # never overwrites an edited strategy
    assert list((ROOT / "vinu-strategy" / "strategies").glob("*.yaml")), "no shipped strategies to seed"


# ------------------------------------------------------------- every service the agent calls has an address in Docker

def test_every_service_url_the_agent_defaults_to_localhost_is_set_in_the_env_example():
    """vinu-agent/config.py reads VINU_<X>_API_URL with a `http://localhost:<port>` fallback. Inside Docker localhost is the
    container itself, so a missing entry in .env-example silently breaks every call to that service (the reflection API
    had none: every reflection read in the agent failed with 'connection refused')."""
    config_text = (ROOT / "vinu-agent" / "vinu_agent" / "config.py").read_text(encoding="utf-8")
    pairs = re.findall(r'os\.environ\.get\("(VINU_[A-Z_]+_API_URL)",\s*"http://localhost:\d+"\)', config_text)
    assert len(pairs) >= 8, "the scan found too few service URLs; the pattern needs updating"
    example = (ROOT / ".env-example").read_text(encoding="utf-8")
    missing = [var for var in pairs if not re.search(rf"^{var}=http://", example, re.M)]
    assert not missing, f".env-example has no address for: {missing}"


def test_the_reflection_container_serves_its_api_as_well_as_running_the_worker():
    script = (ROOT / "vinu-reflection" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "vinu-reflection serve" in script and "vinu-reflection worker" in script


# --------------------------------------------------------- only validated strategies may trade (do not switch this off)

def test_the_seeded_mandate_requires_an_active_artifact():
    """`require_active_artifact` is the gate that only lets a strategy trade after research and simulation passed it. It was
    once switched off for paper trading and unvalidated 15-minute/1-hour strategies went live. It must stay on."""
    script = (ROOT / "vinu-agent" / "entrypoint.sh").read_text(encoding="utf-8")
    assert re.search(r"^require_active_artifact:\s*true\s*$", script, re.M)
    assert not re.search(r"^require_active_artifact:\s*false", script, re.M)


def test_the_live_decision_validation_gate_is_never_switched_off_in_deployment_files():
    """A strategy may open positions only after research validated its exact rules. Setting this to false in compose or an
    env file is how unvalidated 15-minute/1-hour strategies went live; a deliberate local override belongs in a shell."""
    flag = "VINU_LIVE_DECISION_REQUIRE_VALIDATED_STRATEGY"
    for name in (".env-example", ".env", "docker-compose.yml"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if flag in line and not line.lstrip().startswith("#"):
                assert not re.search(r"(false|0|no)\s*[\"']?\s*$", line.split(flag, 1)[1], re.I), f"{name}: {line.strip()}"


def test_the_planner_is_pointed_at_a_screener_ranker_and_takes_the_top_ten():
    """Without VINU_AGENT_SCREENER_RANKER_ID the planner worker cycles with an empty ticker list: screener -> planner is
    unconnected and nothing downstream (analysis, research, strategy) is ever triggered by the screener."""
    example = (ROOT / ".env-example").read_text(encoding="utf-8")
    assert re.search(r"^VINU_AGENT_SCREENER_RANKER_ID=\S+", example, re.M)
    assert re.search(r"^VINU_AGENT_SCREENER_TOP_N=10\s*$", example, re.M)
