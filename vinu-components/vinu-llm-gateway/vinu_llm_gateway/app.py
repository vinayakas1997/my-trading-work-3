"""HTTP face of the gateway: an OpenAI-compatible /v1/chat/completions plus read-only views of the queue."""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from vinu_llm_gateway.gateway import Gateway, GatewayConfig, GatewayFailure, Rejected


def create_app(gateway: Gateway | None = None) -> FastAPI:
    started = time.time()
    holder: dict[str, Gateway] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        gw = gateway or Gateway(GatewayConfig.from_env())
        holder["gw"] = gw
        gw.start(worker_count=int(os.environ.get("VINU_LLM_GATEWAY_SLOTS", "1")))
        try:
            yield
        finally:
            await gw.stop()

    app = FastAPI(title="vinu-llm-gateway", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "vinu-llm-gateway", "uptime_sec": round(time.time() - started, 1)}

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            return _error(400, "request body is not valid JSON")
        if not isinstance(body, dict):
            return _error(400, "request body must be a JSON object")
        try:
            return JSONResponse(await holder["gw"].submit(body, dict(request.headers)))
        except Rejected as exc:
            return _error(exc.status, exc.message)
        except GatewayFailure as exc:
            return _error(exc.status, exc.message)

    @app.get("/llm/queue")
    def queue() -> dict[str, Any]:
        gw = holder["gw"]
        return {**gw.store.stats(), "counters": gw.counters}

    @app.get("/llm/history")
    def history(limit: int = Query(100, ge=1, le=1000), caller: str | None = None) -> dict[str, Any]:
        return {"rows": holder["gw"].store.history(limit, caller)}

    return app


def _error(status: int, message: str) -> JSONResponse:
    # OpenAI's error shape, so SDK callers raise a readable exception
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": "vinu_llm_gateway"}})
