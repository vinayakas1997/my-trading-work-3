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


def test_the_local_llm_context_is_big_enough_for_the_agent_teams():
    """16K made the local server answer 'Context size has been exceeded' to the screener team's prompts."""
    example = (ROOT / ".env-example").read_text(encoding="utf-8")
    ctx = int(re.search(r"^HINDSIGHT_LLM_CTX_SIZE=(\d+)\s*$", example, re.M).group(1))
    assert ctx >= 40000


def test_the_local_llm_runs_one_slot_so_concurrent_prompts_queue_instead_of_overflowing():
    """n_slots=4 with kv_unified shared one 40K pool: three concurrent ~15K-token prompts answered 'Context size has
    been exceeded'. One slot makes concurrent requests queue."""
    compose = (ROOT / "docker-compose-hindsight.yml").read_text(encoding="utf-8")
    assert re.search(r"LLAMA_ARG_N_PARALLEL:\s*\$\{HINDSIGHT_LLM_PARALLEL:-1\}", compose)
    example = (ROOT / ".env-example").read_text(encoding="utf-8")
    assert re.search(r"^HINDSIGHT_LLM_PARALLEL=1\s*$", example, re.M)


def test_a_sub_agent_delegation_may_outlast_several_slow_local_llm_calls():
    """60 s cut off most angle_synthesizer delegations (one cluster read is ~30 s on the local 9B model, more when it
    queues), so META's summary came back with 6 of 7 clusters 'timed out'. Tickers also run one at a time, since the
    single LLM slot makes parallel tickers only wait longer."""
    example = (ROOT / ".env-example").read_text(encoding="utf-8")
    assert int(re.search(r"^VINU_AGENT_TOOL_TIMEOUT=(\d+)\s*$", example, re.M).group(1)) >= 600
    assert re.search(r"^VINU_AGENT_SUMMARY_PARALLELISM=1\s*$", example, re.M)


def test_a_stale_container_cannot_go_unnoticed():
    """Fixes only take effect once the image is rebuilt and the container recreated. Seven of eleven running services
    were older than their source (the agent still ran the old research code in-process), so `stack.sh stale` reports
    them and `stack.sh deploy` rebuilds and recreates exactly those."""
    script = (ROOT / "scripts" / "stack.sh").read_text(encoding="utf-8")
    assert re.search(r"^stale\(\)", script, re.M) and re.search(r"^deploy\(\)", script, re.M)
    assert "prepare|check|build|up|down|ps|stale|deploy" in script
    checker = (ROOT / "scripts" / "stale_images.py").read_text(encoding="utf-8")
    assert "docker" in checker and "COPY" in checker and "sys.exit(main())" in checker


def test_no_service_switches_sqlite_to_wal_on_its_own():
    """Switching a file to WAL races when several connections open it together ("database is locked", instantly, past
    the busy timeout). vinu_infra.db.enable_wal retries; a service that writes the pragma itself brings the race back."""
    offenders = []
    for path in ROOT.glob("vinu-*/**/*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if "/tests/" in rel or rel in ("vinu-infra/db.py", "vinu-infra/sqlite.py"):
            continue
        if re.search(r"""execute\(\s*["']PRAGMA journal_mode\s*=\s*WAL""", path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(rel)
    assert offenders == [], f"use vinu_infra.db.enable_wal instead of the raw pragma in: {offenders}"


def test_deploy_does_not_abort_when_the_stale_check_exits_nonzero():
    """stale_images.py exits 1 when something is stale. `stack.sh deploy` captured its output under
    `set -euo pipefail`, so the first time anything WAS stale the script stopped silently without rebuilding."""
    script = (ROOT / "scripts" / "stack.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    capture = re.search(r"names=\$\(python scripts/stale_images\.py[^\n]*\)", script)
    assert capture and "|| true" in capture.group(0)


def test_every_shell_script_parses():
    """scripts/test_in_containers.sh was committed with an apostrophe inside a single-quoted block and did not parse.
    A script that does not parse fails at the moment it is needed."""
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if bash is None:
        import pytest

        pytest.skip("bash not available")
    bad = []
    for script in sorted((ROOT / "scripts").glob("*.sh")) + sorted(ROOT.glob("vinu-*/entrypoint.sh")):
        result = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
        if result.returncode != 0:
            bad.append(f"{script.name}: {result.stderr.strip()[:120]}")
    assert bad == [], bad


def test_stale_check_sees_an_uncommitted_edit_when_the_folder_is_a_subdirectory_of_the_repo(tmp_path, monkeypatch):
    """git status prints repo-root-relative paths; joining them to a sub-folder found no file, so an edited but
    uncommitted source never made its image look stale (a deploy then rebuilt nothing)."""
    import importlib.util
    import subprocess
    import time

    spec = importlib.util.spec_from_file_location("stale_images", Path(__file__).resolve().parents[2] / "scripts" / "stale_images.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sub = tmp_path / "sub"
    (sub / "pkg").mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (sub / "pkg" / "a.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-q", "-m", "first")
    time.sleep(1.1)
    (sub / "pkg" / "a.py").write_text("x = 2\n")           # edited, not committed
    monkeypatch.setattr(mod, "ROOT", sub)
    changed_at, what = mod.newest_change(["pkg"])
    assert "uncommitted edit" in what and changed_at >= (sub / "pkg" / "a.py").stat().st_mtime - 1


def test_committing_what_an_image_was_built_from_does_not_make_it_stale(tmp_path, monkeypatch):
    """Build, test, then commit is the normal order. The commit time is later than the build, but the files are the ones
    the image was built from; judging by commit time flagged every service stale until the next real change."""
    import importlib.util
    import os
    import subprocess

    spec = importlib.util.spec_from_file_location("stale_images", Path(__file__).resolve().parents[2] / "scripts" / "stale_images.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    (tmp_path / "pkg").mkdir()
    f = tmp_path / "pkg" / "a.py"
    f.write_text("x = 1\n")
    git = lambda *a, **k: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True, **k)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("add", ".")
    future = str(int(f.stat().st_mtime) + 86_400)               # the commit is dated a day AFTER the file was written
    git("commit", "-q", "-m", "after the build", env={**os.environ, "GIT_COMMITTER_DATE": future, "GIT_AUTHOR_DATE": future})
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    changed_at, _ = mod.newest_change(["pkg"])
    assert changed_at <= f.stat().st_mtime + 1


def test_a_container_whose_image_was_removed_is_reported_stale_not_a_crash():
    text = (Path(__file__).resolve().parents[2] / "scripts" / "stale_images.py").read_text(encoding="utf-8")
    assert "the container's image no longer exists" in text


def test_model_angles_are_switched_off_while_the_models_service_is_dormant():
    """models-api only starts under a compose profile. With VINU_MODELS_ENABLED unset the analysis service tried every
    model angle on every ticker each cycle, failed on the missing host, and logged ~100 tracebacks per 6 minutes that
    buried the real errors."""
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    env = (root / ".env-example").read_text(encoding="utf-8")
    dormant = re.search(r"^  models-api:\r?\n(?:.*\r?\n)*?    profiles:", compose, re.M) is not None
    assert dormant, "models-api is expected to sit behind a compose profile; update this guard if that changed"
    if dormant:
        assert re.search(r"^VINU_MODELS_ENABLED=false\s*$", env, re.M), "set VINU_MODELS_ENABLED=false in .env-example"


def test_every_team_purpose_is_one_the_gateway_knows():
    """A team mapped to a purpose the gateway's table lacks would have every one of its LLM calls rejected (400)."""
    import ast
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "vinu-agent/vinu_agent/agent/team.py").read_text(encoding="utf-8"))
    mapping = next(
        ast.literal_eval(n.value) for n in ast.walk(tree)
        if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "TEAM_PURPOSE"
    )
    spec = importlib.util.spec_from_file_location("gw_priorities", root / "vinu-llm-gateway/vinu_llm_gateway/priorities.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    unknown = {t: p for t, p in mapping.items() if p not in mod.PURPOSE_PRIORITY}
    assert not unknown, f"purposes missing from the gateway table: {unknown}"
    assert mapping["live_decision"] == "live_decision" and mod.PURPOSE_PRIORITY["live_decision"] == 1


def test_no_script_or_container_entrypoint_has_windows_line_endings():
    """An entrypoint saved with CRLF makes `#!/bin/bash\r` unresolvable: the container dies with 'exec /app/entrypoint.sh:
    no such file or directory' and restarts forever (an edit of the agent's entrypoint from Windows did exactly that).
    bash -n does not notice, so check the bytes."""
    root = Path(__file__).resolve().parents[2]
    bad = []
    for path in list(root.glob("*/entrypoint.sh")) + list((root / "scripts").glob("*.sh")):
        if b"\r" in path.read_bytes():
            bad.append(str(path.relative_to(root)))
    assert not bad, f"CRLF line endings (run: sed -i 's/\r$//' <file>): {bad}"


def test_stale_check_sees_a_changed_file_that_git_considers_unchanged(tmp_path, monkeypatch):
    """Git normalises line endings, so an entrypoint re-saved with CRLF looks clean to `git status` while the next build
    copies different bytes; the deploy then rebuilt nothing and the container crash-looped. The file's modification
    time is checked directly."""
    import importlib.util
    import subprocess
    import time

    spec = importlib.util.spec_from_file_location("stale_images2", Path(__file__).resolve().parents[2] / "scripts" / "stale_images.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sub = tmp_path / "sub"
    (sub / "pkg").mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    f = sub / "pkg" / "entrypoint.sh"
    f.write_bytes(b"#!/bin/bash\necho hi\n")
    git("add", ".")
    git("commit", "-q", "-m", "first")
    time.sleep(1.1)
    f.write_bytes(b"#!/bin/bash\r\necho hi\r\n")             # different bytes, same content to git after normalisation
    (tmp_path / ".gitattributes").write_text("*.sh text eol=lf\n")
    monkeypatch.setattr(mod, "ROOT", sub)
    mtime, which = mod.newest_mtime(["pkg"])
    assert which.endswith("entrypoint.sh") and mtime >= f.stat().st_mtime - 1
    # tests and docs never reach a running service, so changing them must not make an image look stale
    # (the folders and files exist before the baseline: ADDING an entry to a source folder is a change to what a build
    # copies and is caught by the directory check; editing a test or a doc that is already there is not)
    (sub / "pkg" / "tests").mkdir()
    (sub / "pkg" / "tests" / "test_x.py").write_text("x")
    (sub / "pkg" / "README.md").write_text("x")
    baseline_mtime = mod.newest_mtime(["pkg"])[0]
    time.sleep(1.1)
    (sub / "pkg" / "tests" / "test_x.py").write_text("changed")
    (sub / "pkg" / "README.md").write_text("changed")
    assert mod.newest_mtime(["pkg"])[0] == baseline_mtime
    assert mod.newest_change(["pkg"])[0] >= mtime


def test_moving_or_deleting_a_file_makes_an_image_stale(tmp_path, monkeypatch):
    """A stray package folder was created, built into images, then moved away: no remaining file changed, so the stale
    check said 'nothing is stale' over images built with the wrong layout. A directory's modification time changes when an
    entry is added, removed or renamed in it, so the check now watches directories too."""
    import importlib.util
    import os
    import time

    spec = importlib.util.spec_from_file_location("stale_images", Path(__file__).resolve().parents[2] / "scripts" / "stale_images.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pkg = tmp_path / "pkg"
    (pkg / "inner").mkdir(parents=True)
    keep = pkg / "keep.py"
    keep.write_text("x = 1\n")
    (pkg / "inner" / "stray.py").write_text("y = 1\n")
    old = time.time() - 1000
    for f in (keep, pkg / "inner" / "stray.py", pkg / "inner", pkg):
        os.utime(f, (old, old))
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    before, _ = mod.newest_mtime(["pkg"])
    (pkg / "inner" / "stray.py").unlink()                    # no remaining file is touched
    after, which = mod.newest_mtime(["pkg"])
    assert after > before and "directory changed" in which


def test_every_shared_module_the_code_imports_exists_where_the_package_expects_it():
    """`vinu_infra` is the folder vinu-infra/ itself (pyproject maps the package name to "."), so `from vinu_infra.sessions import X`
    needs vinu-infra/sessions.py. A new module put under vinu-infra/vinu_infra/ imports fine in a unit test and crash-loops the container."""
    import re

    root = Path(__file__).resolve().parents[2]
    shared = root / "vinu-infra"
    pattern = re.compile(r"^\s*(?:from|import)\s+vinu_infra\.([A-Za-z_][A-Za-z0-9_]*)", re.M)
    missing: dict[str, str] = {}
    for py in root.glob("vinu-*/**/*.py"):
        if "tests" in py.parts or "__pycache__" in py.parts or ".venv" in py.parts:
            continue
        for name in pattern.findall(py.read_text(encoding="utf-8", errors="replace")):
            if not ((shared / f"{name}.py").is_file() or (shared / name / "__init__.py").is_file()):
                missing[name] = str(py.relative_to(root))
    assert not missing, f"imported from vinu_infra but not found in vinu-infra/: {missing}"


def test_the_angle_counts_written_in_the_requirements_pack_match_the_code():
    """The pack says how many analysis angles are in scope (models are off, so model angles are out of scope). A count written in a
    document must not drift from the angle specs, or "how many angles ran" gets answered against the wrong number again."""
    root = Path(__file__).resolve().parents[2]
    specs = list((root / "vinu-initial-analysis" / "vinu_initial_analysis" / "angles").glob("*/spec.yaml"))
    categories = [re.search(r"^category:\s*(\w+)", p.read_text(encoding="utf-8"), re.M).group(1) for p in specs]
    registered, models = len(categories), categories.count("model")
    import ast

    manifest = (root / "vinu-infra" / "system_manifest.py").read_text(encoding="utf-8")
    switched_off = len(ast.literal_eval(re.search(r"^PERMANENTLY_DISABLED_ANGLES[^=]*=\s*frozenset\((\{.*?\}|)\)", manifest, re.M | re.S).group(1) or "set()"))
    doc = root.parent / "Proper-Project-Implementation" / "00-project-understanding" / "analysis-angles-in-scope.md"
    if not doc.is_file():
        pytest.skip("requirements pack not present in this checkout")
    text = doc.read_text(encoding="utf-8")
    keys = ("REGISTERED ANGLES", "MODEL ANGLES", "SWITCHED-OFF ANGLES", "IN-SCOPE ANGLES")
    written = {k: int(re.search(rf"^{k}:\s*(\d+)", text, re.M).group(1)) for k in keys}
    assert written == {"REGISTERED ANGLES": registered, "MODEL ANGLES": models, "SWITCHED-OFF ANGLES": switched_off,
                       "IN-SCOPE ANGLES": registered - models - switched_off}


def test_every_setting_in_the_env_example_is_read_by_something():
    """A setting nothing reads is a switch that does nothing: the correlation block (market-hours-only, session-break-on-close
    and ten more) belonged to a service that no longer exists, yet it looked like it controlled analysis hours (problem log O2).
    A name is read when it appears in a service's code, the compose file or a script."""
    names = set(re.findall(r"^#?\s*(VINU_[A-Z0-9_]+)=", (ROOT / ".env-example").read_text(encoding="utf-8"), re.M))
    assert len(names) > 100, "the scan found too few settings; the pattern needs updating"
    blob = []
    for base in [p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("vinu-")] + [ROOT / "scripts"]:
        blob += [f.read_text(encoding="utf-8", errors="ignore") for f in base.rglob("*")
                 if f.suffix in (".py", ".sh", ".yml", ".yaml") and "tests" not in f.parts and "__pycache__" not in f.parts]
    blob += [f.read_text(encoding="utf-8", errors="ignore") for f in ROOT.glob("*") if f.is_file() and f.suffix in (".py", ".yml", ".sh")]
    text = "\n".join(blob)
    unread = sorted(n for n in names if n not in text and n not in READ_ONLY_BY_THE_TEST_HARNESS)
    assert not unread, f".env-example lists settings no code reads: {unread}"


# read by scripts/test_in_containers.sh, which greps the template for every *_DATA_ROOT name
READ_ONLY_BY_THE_TEST_HARNESS = {"VINU_NEWS_DATA_ROOT"}


def test_the_env_example_keeps_the_full_history_start_date_not_the_short_test_override():
    """VINU_STAGE1_START_DATE=2026-06-17 was a two-week plumbing check left in place: every analysis window became a few months
    long (problem log O1). The template must carry the real origin."""
    text = (ROOT / ".env-example").read_text(encoding="utf-8")
    values = re.findall(r"^VINU_STAGE1_START_DATE=(\S+)", text, re.M)
    assert values == ["2022-01-01"], values


def test_the_infra_tests_run_in_an_empty_folder_so_they_cannot_leave_databases_among_the_real_ones():
    import os

    assert Path.cwd().resolve() != ROOT.resolve() and not os.listdir(Path.cwd())


def test_every_long_running_service_in_the_compose_file_has_a_health_check():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    body = compose.partition("services:")[2]
    services = re.split(r"^  (?=[a-z][a-z0-9-]*:\s*$)", body, flags=re.M)
    missing = [s.split(":", 1)[0] for s in services if "    build:" in s and "healthcheck:" not in s]
    assert not missing, f"no health check: {missing}"


def test_deploy_refuses_to_restart_the_research_services_while_a_run_is_in_flight():
    """A deploy killed 24 of the 30 research runs that failed in one day (problem log O7, O17)."""
    script = (ROOT / "scripts" / "stack.sh").read_text(encoding="utf-8")
    assert "refusing to deploy" in script and 'FORCE:-}" != "1"' in script
    assert "status='running'" in script and "agent-api|research-api|llm-gateway|quant-core-api" in script
