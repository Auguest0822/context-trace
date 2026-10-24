"""HTTP boundary for the original conversation archive.

Run with ``uvicorn yanji.server.api:app --host 127.0.0.1 --port 8000``.
Storage rules and SQL remain in :mod:`yanji.store.repo`.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from pymysql.err import IntegrityError, InterfaceError, OperationalError

from yanji.models import (
    ConversationInput,
    ExtractionCommitInput,
    ExtractionPreviewInput,
    MemoryContextInput,
    MemoryHandoffInput,
    MemoryKind,
    MemoryReconcileInput,
    MemorySearchInput,
    MemoryWriteInput,
    MessageAppendInput,
)
from yanji.store import memory_repo, repo, retrieval, trace_repo, version_repo
from yanji.store.client import check_connection

try:
    from yanji.server.mcp_server import mcp
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    mcp = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    if mcp is None:
        yield
    else:
        async with mcp.session_manager.run():
            yield


app = FastAPI(title="ContextTrace API", version="0.1.0", lifespan=lifespan)

# The console is a separate Vite origin during local development. Deployment may
# set an explicit comma-separated list; an empty value disables browser CORS.
_origins = os.getenv(
    "YANJI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
)

Scope = Annotated[str, Query(min_length=1, max_length=128)]
ConversationId = Annotated[str, Path(pattern=r"^[1-9][0-9]*$")]
PreviewId = Annotated[str, Path(pattern=r"^[0-9a-fA-F-]{36}$")]
TraceId = Annotated[str, Path(pattern=r"^[0-9a-fA-F-]{36}$")]
Platform = Literal["deepseek", "kimi", "doubao", "agent", "other"]
MemoryStatus = Literal["active", "superseded", "expired"]


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


@app.exception_handler(memory_repo.PreviewExpired)
async def preview_expired(request: Request, exc: memory_repo.PreviewExpired) -> JSONResponse:
    return _error(request, 410, "PREVIEW_EXPIRED", str(exc))


@app.exception_handler(retrieval.EmbeddingUnavailable)
async def embedding_unavailable(request: Request, exc: retrieval.EmbeddingUnavailable) -> JSONResponse:
    return _error(request, 422, "EMBEDDING_UNAVAILABLE", str(exc))


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
        raise ValueError(f"unknown query parameter: {min(unknown)}")


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


@app.post("/v1/extractions/preview")
def preview_extraction(request: Request, data: ExtractionPreviewInput) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return memory_repo.create_manual_preview(data)


@app.post("/v1/extractions/{preview_id}/commit")
def commit_extraction(
    request: Request, preview_id: PreviewId, data: ExtractionCommitInput
) -> JSONResponse:
    _reject_unknown_query(request, set())
    result = memory_repo.commit_manual_preview(preview_id, data)
    created = result.pop("created")
    return JSONResponse(status_code=201 if created else 200, content=result)


@app.get("/v1/memories/{memory_id}")
def get_memory(request: Request, memory_id: ConversationId, scope: Scope) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope"})
    return {"memory": memory_repo.get_memory(_check_scope(scope), memory_id)}


@app.post("/v1/memories")
def write_memory(request: Request, data: MemoryWriteInput) -> JSONResponse:
    _reject_unknown_query(request, set())
    result = memory_repo.write_memory(data)
    return JSONResponse(status_code=201 if result.pop("created") else 200, content=result)


@app.get("/v1/memories")
def list_memories(
    request: Request, scope: Scope, status: MemoryStatus | None = None,
    kind: MemoryKind | None = None, platform: Platform | None = None,
    conversation_id: Annotated[str | None, Query(pattern=r"^[1-9][0-9]*$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    _reject_unknown_query(
        request, {"scope", "status", "kind", "platform", "conversation_id", "limit", "cursor"}
    )
    return retrieval.list_memories(
        _check_scope(scope), status=status, kind=kind, platform=platform,
        conversation_id=conversation_id, limit=limit, cursor=cursor,
    )


@app.post("/v1/memories/search")
def search_memories(request: Request, data: MemorySearchInput) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return retrieval.search_memories(data)


@app.post("/v1/memories/context")
def assemble_context(request: Request, data: MemoryContextInput) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return retrieval.assemble_context(data)


@app.post("/v1/memories/reconcile")
def reconcile_memory(request: Request, data: MemoryReconcileInput) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return version_repo.reconcile(data)


@app.get("/v1/memories/{memory_id}/history")
def memory_history(request: Request, memory_id: ConversationId, scope: Scope) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope"})
    return version_repo.history(_check_scope(scope), memory_id)


@app.delete("/v1/memories/{memory_id}")
def forget_memory(request: Request, memory_id: ConversationId, scope: Scope) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope"})
    return version_repo.forget(_check_scope(scope), memory_id)


@app.get("/v1/traces")
def list_traces(
    request: Request, scope: Scope, limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope", "limit", "cursor"})
    return trace_repo.list_traces(_check_scope(scope), limit=limit, cursor=cursor)


@app.get("/v1/traces/{trace_id}")
def get_trace(request: Request, trace_id: TraceId, scope: Scope) -> dict[str, Any]:
    _reject_unknown_query(request, {"scope"})
    return trace_repo.get_trace(_check_scope(scope), trace_id)


@app.post("/v1/memories/handoff")
def handoff(request: Request, data: MemoryHandoffInput) -> dict[str, Any]:
    _reject_unknown_query(request, set())
    return retrieval.handoff(data)


if mcp is not None:
    # Mount last: the root mount matches every URL, so REST routes take priority.
    app.mount("/", mcp.streamable_http_app(json_response=True))
