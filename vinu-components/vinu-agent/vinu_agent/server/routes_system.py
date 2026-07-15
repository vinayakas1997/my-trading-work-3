import time as _time
from typing import Any

from fastapi import APIRouter

from ..service import AgentService
from .schemas import HealthResponse

router = APIRouter()
_get_service: Any = lambda: None

_START_TIME = _time.time()


@router.get("/health", response_model=HealthResponse)
async def health():
    svc: AgentService = _get_service()
    status = svc.get_status()
    return HealthResponse(
        status="ok",
        service="vinu-agent",
        uptime_seconds=_time.time() - _START_TIME,
        active_sessions=status["active_sessions"],
        skills_loaded=status["skills_loaded"],
        llm_provider=status["llm_provider"],
        llm_model=status["llm_model"],
    )


@router.get("/status")
async def status():
    svc: AgentService = _get_service()
    return svc.get_status()
