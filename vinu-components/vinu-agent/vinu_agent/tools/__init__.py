import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..agent.tools import BaseTool, ToolRegistry

_SUBCLASSES_CACHE: list = []


def _discover_subclasses() -> list:
    global _SUBCLASSES_CACHE
    if _SUBCLASSES_CACHE:
        return _SUBCLASSES_CACHE

    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name.startswith("_"):
            continue
        importlib.import_module(f".{module_name}", package=__package__)

    # Real fix: BaseTool.__subclasses__() is process-global, not scoped to
    # this package -- any BaseTool subclass defined anywhere in the
    # codebase becomes "discoverable" here the instant its module is
    # imported by anything, even transitively (e.g. agent/team.py's
    # DelegateToAgentTool, which requires constructor args and is built
    # per-team on purpose, not meant to be auto-registered). Only count
    # subclasses actually defined inside this tools/ package.
    _SUBCLASSES_CACHE = [
        cls for cls in BaseTool.__subclasses__()
        if cls.__module__.startswith(f"{__package__}.")
    ]
    return _SUBCLASSES_CACHE


def build_registry(
    *,
    persistent_memory: Any = None,
    unified_memory: Any = None,
    session_id: str = "",
    event_callback: Optional[Callable] = None,
    services_config: Optional[dict] = None,
    skills_loader: Any = None,
    session_service: Any = None,
    workflow_tracker: Any = None,
    as_of: Optional[str] = None,
    llm: Any = None,
    teams_dir: str = "",
    run_store: Any = None,
    llm_call_store: Any = None,
    strategy_store: Any = None,
    ticker_summary_store: Any = None,
    ticker_ledger_store: Any = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    subclasses = _discover_subclasses()

    for cls in subclasses:
        if not cls.check_available():
            continue
        tool = cls()
        if hasattr(tool, "_persistent_memory"):
            tool._persistent_memory = persistent_memory
        if hasattr(tool, "_unified_memory"):
            tool._unified_memory = unified_memory
        if hasattr(tool, "_session_id"):
            tool._session_id = session_id
        if hasattr(tool, "_event_callback"):
            tool._event_callback = event_callback
        if services_config and hasattr(tool, "_services_config"):
            tool._services_config = services_config
        if skills_loader and hasattr(tool, "_skills_loader"):
            tool._skills_loader = skills_loader
        if session_service and hasattr(tool, "_session_service"):
            tool._session_service = session_service
        if workflow_tracker and hasattr(tool, "_workflow_tracker"):
            tool._workflow_tracker = workflow_tracker
        if as_of is not None and hasattr(tool, "_as_of"):
            tool._as_of = as_of
        if llm is not None and hasattr(tool, "_llm"):
            tool._llm = llm
        if teams_dir and hasattr(tool, "_teams_dir"):
            tool._teams_dir = teams_dir
        if run_store is not None and hasattr(tool, "_run_store"):
            tool._run_store = run_store
        if llm_call_store is not None and hasattr(tool, "_llm_call_store"):
            tool._llm_call_store = llm_call_store
        if strategy_store is not None and hasattr(tool, "_strategy_store"):
            tool._strategy_store = strategy_store
        if ticker_summary_store is not None and hasattr(tool, "_ticker_summary_store"):
            tool._ticker_summary_store = ticker_summary_store
        if ticker_ledger_store is not None and hasattr(tool, "_ticker_ledger_store"):
            tool._ticker_ledger_store = ticker_ledger_store
        # Tools that need to reach the full tool pool (e.g. delegate_to_team,
        # which builds a scoped sub-registry for each team) get a
        # self-reference to the registry being built here, once construction
        # finishes -- see the loop below.
        registry.register(tool)

    for tool in registry.all_tools():
        if hasattr(tool, "_full_registry"):
            tool._full_registry = registry

    return registry
