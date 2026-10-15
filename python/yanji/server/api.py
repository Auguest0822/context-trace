"""HTTP boundary for the original conversation archive.

Run with ``uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000``.
Storage rules and SQL remain in :mod:`yanji.store.repo`.
"""

from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from pymysql.err import IntegrityError, InterfaceError, OperationalError

from yanji.models import ConversationInput, MessageAppendInput
from yanji.store import repo
from yanji.store.client import check_connection

logger = logging.getLogger(__name__)

app = FastAPI(title="ContextTrace API", version="0.1.0")

# The console is a separate Vite origin during local development. Deployment may
# set an explicit comma-separated list; an empty value disables browser CORS.
_origins = os.getenv(
    "YANJI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)

Scope = Annotated[str, Query(min_length=1, max_length=128)]
ConversationId = Annotated[str, Path(pattern=r"^[1-9][0-9]*$")]
Platform = Literal["deepseek", "kimi", "doubao", "agent", "other"]


@app.middleware("http")
async def attach_request_id(request: Request, call_next: Any) -> Any:
    request.state.request_id = str(uuid4())
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s error_code=%s elapsed_ms=%.1f",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        getattr(request.state, "error_code", "-"),
        (perf_counter() - started) * 1000,
    )
    return response


def _error(
    request: Request, status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    request.state.error_code = code
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request.state.request_id,
        }},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"])
    return _error(
        request, 400, "VALIDATION_ERROR", "Invalid request parameters or JSON body",
        {"field": field, "reason": first["type"]},
    )


@app.exception_handler(repo.NotFound)
async def not_found(request: Request, exc: repo.NotFound) -> JSONResponse:
    return _error(request, 404, "NOT_FOUND", str(exc))


@app.exception_handler(repo.IdempotencyConflict)
async def idempotency_conflict(request: Request, exc: repo.IdempotencyConflict) -> JSONResponse:
    return _error(request, 409, "IDEMPOTENCY_CONFLICT", str(exc))


@app.exception_handler(repo.StateConflict)
async def state_conflict(request: Request, exc: repo.StateConflict) -> JSONResponse:
    return _error(request, 409, "STATE_CONFLICT", str(exc))


@app.exception_handler(IntegrityError)
async def integrity_conflict(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("request_id=%s database integrity conflict", request.state.request_id)
    return _error(request, 409, "STATE_CONFLICT", "The archived data conflicts with existing data")


@app.exception_handler(ValueError)
async def invalid_value(request: Request, exc: ValueError) -> JSONResponse:
    return _error(request, 400, "VALIDATION_ERROR", str(exc))


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def store_unavailable(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("request_id=%s seekdb unavailable (%s)", request.state.request_id, type(exc).__name__)
    return _error(request, 503, "STORE_UNAVAILABLE", "seekdb is unavailable")


def _reject_unknown_query(request: Request, allowed: set[str]) -> None:
    unknown = set(request.query_params) - allowed
    if unknown:
        raise ValueError(f"unknown query parameter: {sorted(unknown)[0]}")


def _check_scope(scope: str) -> str:
    if not scope.strip():
        raise ValueError("scope cannot be blank")
    return scope


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(request: Request) -> Any:
    try:
        if check_connection():
            return {"status": "ok"}
    except (OperationalError, InterfaceError):
        pass
    return _error(request, 503, "STORE_UNAVAILABLE", "seekdb is unavailable")


@app.post("/v1/conversations")
def capture_conversation(request: Request, data: ConversationInput) -> JSONResponse:
    _reject_unknown_query(request, set())
    result = repo.capture_conversation(data)
    created = result.pop("created")
    return JSONResponse(status_code=201 if created else 200, content=result)


@app.post("/v1/conversations/{conversation_id}/messages")
def append_messages(
    request: Request, conversation_id: ConversationId, data: MessageAppendInput
) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return repo.append_messages(conversation_id, data)


@app.get("/v1/conversations")
def list_conversations(
    request: Request,
    scope: Scope,
    platform: Platform | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    captured_from: AwareDatetime | None = None,
    captured_to: AwareDatetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    _reject_unknown_query(
        request, {"scope", "platform", "q", "captured_from", "captured_to", "limit", "cursor"}
    )
    return repo.list_conversations(
        _check_scope(scope), platform=platform, q=q, captured_from=captured_from,
        captured_to=captured_to, limit=limit, cursor=cursor,
    )


@app.get("/v1/conversations/{conversation_id}")
def get_conversation(
    request: Request, conversation_id: ConversationId, scope: Scope
) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope"})
    return {"conversation": repo.get_conversation(_check_scope(scope), conversation_id)}


@app.get("/v1/conversations/{conversation_id}/messages")
def list_messages(
    request: Request,
    conversation_id: ConversationId,
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope", "limit", "cursor"})
    return repo.list_messages(_check_scope(scope), conversation_id, limit=limit, cursor=cursor)
