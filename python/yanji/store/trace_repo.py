"""Read persisted retrieval decisions; never infer explanations after the fact."""

from __future__ import annotations

import json
from typing import Any

from yanji.store.client import connect
from yanji.store.repo import NotFound, _decode_cursor, _encode_cursor, _timestamp


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    budget = _json(row["budget"])
    return {
        "trace_id": row["trace_id"], "scope": row["scope"], "query": row["query"],
        "mode_requested": row["mode_requested"], "mode_used": row["mode_used"],
        "filters_applied": _json(row["filters_applied"]),
        "candidate_count": row["candidate_count"], "selected_count": row["selected_count"],
        "budget": budget, "elapsed_ms": row["elapsed_ms"],
        "created_at": _timestamp(row["created_at"]),
    }


def list_traces(scope: str, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
    if not scope.strip() or not 1 <= limit <= 100:
        raise ValueError("invalid scope or limit")
    clauses = ["scope = %s"]
    params: list[Any] = [scope]
    if cursor:
        cursor_scope, created, trace_id = _decode_cursor(cursor, 3)
        if cursor_scope != scope:
            raise ValueError("cursor does not match the requested scope")
        clauses.append("(created_at < %s OR (created_at = %s AND trace_id < %s))")
        params.extend([created, created, trace_id])
    sql = ("SELECT * FROM retrieval_traces WHERE " + " AND ".join(clauses)
           + " ORDER BY created_at DESC, trace_id DESC LIMIT %s")
    with connect() as connection, connection.cursor() as db_cursor:
        db_cursor.execute(sql, (*params, limit + 1))
        rows = db_cursor.fetchall()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(scope, last["created_at"].isoformat(sep=" "),
                                     last["trace_id"])
    return {"items": [_summary(row) for row in page], "next_cursor": next_cursor}


def get_trace(scope: str, trace_id: str) -> dict[str, Any]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT * FROM retrieval_traces WHERE scope = %s AND trace_id = %s",
                       (scope, trace_id))
        row = cursor.fetchone()
        if row is None:
            raise NotFound("trace not found in this scope")
        cursor.execute(
            "SELECT memory_id, keyword_rank, vector_rank, fusion_score, decision, "
            "selected_form, reason_codes FROM retrieval_trace_items "
            "WHERE scope = %s AND trace_id = %s ORDER BY fusion_rank ASC",
            (scope, trace_id),
        )
        candidates = [{
            "memory_id": str(item["memory_id"]),
            "keyword_rank": item["keyword_rank"], "vector_rank": item["vector_rank"],
            "fusion_score": item["fusion_score"], "decision": item["decision"],
            "selected_form": item["selected_form"],
            "reason_codes": _json(item["reason_codes"]),
        } for item in cursor.fetchall()]
    return {**_summary(row), "candidates": candidates}
