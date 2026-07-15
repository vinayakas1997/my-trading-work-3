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

    _SUBCLASSES_CACHE = list(BaseTool.__subclasses__())
    return _SUBCLASSES_CACHE


def build_registry(
    *,
    persistent_memory: Any = None,
    session_id: str = "",
    event_callback: Optional[Callable] = None,
    services_config: Optional[dict] = None,
    skills_loader: Any = None,
    session_service: Any = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    subclasses = _discover_subclasses()

    for cls in subclasses:
        if not cls.check_available():
            continue
        tool = cls()
        if hasattr(tool, "_persistent_memory"):
            tool._persistent_memory = persistent_memory
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
        registry.register(tool)

    return registry
