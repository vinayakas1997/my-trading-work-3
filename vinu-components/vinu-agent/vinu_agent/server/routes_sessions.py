from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..service import AgentService
from .schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionResponse,
)

router = APIRouter()
_get_service: Any = lambda: None


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    svc: AgentService = _get_service()
    session = await svc.create_session(title=req.title, as_of=req.as_of)
    return CreateSessionResponse(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(limit: int = Query(default=50)):
    svc: AgentService = _get_service()
    sessions = svc._store.list_sessions(limit=limit)
    return [
        SessionResponse(
            session_id=s.session_id,
            title=s.title,
            status=s.status.value,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_attempt_id=s.last_attempt_id,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    svc: AgentService = _get_service()
    session = svc._store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session.session_id,
        title=session.title,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_attempt_id=session.last_attempt_id,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    svc: AgentService = _get_service()
    if svc._store.delete_session(session_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: str, req: SendMessageRequest):
    svc: AgentService = _get_service()
    try:
        result = await svc.send_message(session_id, req.content, as_of=req.as_of)
        return SendMessageResponse(
            message_id=result["message_id"],
            attempt_id=result["attempt_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    svc: AgentService = _get_service()
    cancelled = svc.cancel(session_id)
    return {"cancelled": cancelled}


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(session_id: str, limit: int = Query(default=100)):
    svc: AgentService = _get_service()
    session = svc._store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = svc._store.get_messages(session_id, limit=limit)
    return [
        MessageResponse(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            linked_attempt_id=m.linked_attempt_id,
        )
        for m in messages
    ]


@router.get("/sessions/{session_id}/events")
async def stream_events(session_id: str, last_event_id: str = Query(default="")):
    svc: AgentService = _get_service()

    async def event_stream():
        async for event in svc.event_bus.subscribe(
            session_id, last_event_id or None
        ):
            yield event.to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
