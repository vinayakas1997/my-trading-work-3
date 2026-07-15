from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str = ""


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    message_id: str
    attempt_id: str


class SessionResponse(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    last_attempt_id: Optional[str] = None


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str
    linked_attempt_id: Optional[str] = None


class StartSwarmRequest(BaseModel):
    preset_name: str
    user_vars: Dict[str, str]


class SwarmRunResponse(BaseModel):
    run_id: str
    preset_name: str
    status: str
    final_report: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vinu-agent"
    uptime_seconds: float = 0.0
    active_sessions: int = 0
    skills_loaded: int = 0
    llm_provider: str = ""
    llm_model: str = ""
