"""Scoped memory listing and explainable keyword retrieval.

The keyword path works without an embedding provider. Vector and hybrid modes
use the explicit local 1024-dimensional baseline when enabled; they never
return keyword results under a different mode label.
"""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from yanji import embedding
from yanji.models import (
    MemoryContextInput,
    MemoryHandoffInput,
    MemorySearchInput,
    utc_database_time,
)
from yanji.store.client import connect
from yanji.store.memory_repo import _memory
from yanji.store.repo import (
    NotFound,
    StateConflict,
    _decode_cursor,
    _encode_cursor,
    _request_hash,
    _transaction,
)


class EmbeddingUnavailable(Exception):
    """The requested vector channel is not configured."""


def _with_links(cursor: Any, rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    placeholders = ", ".join(["%s"] * len(rows))
    cursor.execute(
        "SELECT memory_id, message_id FROM memory_message_links "
        f"WHERE scope = %s AND memory_id IN ({placeholders}) "
        "ORDER BY memory_id, message_id",
        (scope, *(row["id"] for row in rows)),
    )
    links: dict[str, list[str]] = {}
    for link in cursor.fetchall():
        links.setdefault(str(link["memory_id"]), []).append(str(link["message_id"]))
    return [_memory(row, links.get(str(row["id"]), [])) for row in rows]


def list_memories(
    scope: str, *, status: str | None = None, kind: str | None = None,
    platform: str | None = None, conversation_id: str | None = None,
    limit: int = 20, cursor: str | None = None,
) -> dict[str, Any]:
    if not scope.strip() or not 1 <= limit <= 100:
        raise ValueError("invalid scope or limit")
    filter_key = _request_hash({
        "status": status, "kind": kind, "platform": platform,
        "conversation_id": conversation_id,
    })
    clauses = ["scope = %s"]
    params: list[Any] = [scope]
    for column, value in (("status", status), ("kind", kind),
                          ("source_platform", platform), ("conversation_id", conversation_id)):
        if value is not None:
            clauses.append(f"{column} = %s")
            params.append(value)
    if cursor is not None:
        cursor_scope, cursor_filters, created, last_id = _decode_cursor(cursor, 4)
        if cursor_scope != scope or cursor_filters != filter_key:
            raise ValueError("cursor does not match the requested scope and filters")
        clauses.append("(created_at < %s OR (created_at = %s AND id < %s))")
        params.extend([created, created, last_id])
    sql = ("SELECT * FROM memories WHERE " + " AND ".join(clauses)
           + " ORDER BY created_at DESC, id DESC LIMIT %s")
    with connect() as connection, connection.cursor() as db_cursor:
        db_cursor.execute(sql, (*params, limit + 1))
        rows = db_cursor.fetchall()
        page = _with_links(db_cursor, rows[:limit], scope)
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(
            scope, filter_key, last["created_at"].isoformat(sep=" "), last["id"]
        )
    return {"items": page, "next_cursor": next_cursor}


def _terms(query: str) -> list[str]:
    terms: list[str] = []
    for group in re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", query.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", group) and len(group) > 2:
            terms.extend(group[i:i + 2] for i in range(len(group) - 1))
        else:
            terms.append(group)
    return list(dict.fromkeys(terms))[:32]


def _estimate_tokens(text: str) -> int:
    # Conservative, deterministic approximation until the tokenizer is fixed.
    return math.ceil(len(text.encode("utf-8")) / 3)


def _select_form(memory: dict[str, Any], used_tokens: int, limit: int,
                 has_previous: bool) -> tuple[str | None, str | None, int]:
    header = f"[memory:{memory['id']} | source:{memory['source_ref']}]\n"
    separator_tokens = _estimate_tokens("\n\n") if has_previous else 0
    for form, body in (("content", memory["content"]), ("summary", memory["summary"])):
        if body:
            rendered = header + body
            count = _estimate_tokens(rendered)
            if used_tokens + separator_tokens + count <= limit:
                return form, rendered, count
    return None, None, 0


def assemble_context(data: MemoryContextInput | dict[str, Any]) -> dict[str, Any]:
    """Compose only user-selected, currently active IDs in the supplied order."""
    request = data if isinstance(data, MemoryContextInput) else MemoryContextInput.model_validate(data)
    if not request.memory_ids:
        rows = []
    else:
        placeholders = ", ".join(["%s"] * len(request.memory_ids))
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM memories WHERE scope = %s AND id IN ({placeholders})",
                (request.scope, *request.memory_ids),
            )
            rows = cursor.fetchall()
    by_id = {str(row["id"]): row for row in rows}
    if set(request.memory_ids) != set(by_id):
        raise NotFound("a selected memory was not found in this scope")
    items = []
    excluded = []
    context_parts: list[str] = []
    used_tokens = 0
    now = datetime.now(UTC).replace(tzinfo=None)
    for memory_id in request.memory_ids:
        row = by_id[memory_id]
        if (row["status"] != "active" or
            (row["valid_from"] is not None and row["valid_from"] > now) or
            (row["valid_to"] is not None and row["valid_to"] <= now)):
            raise StateConflict("a selected memory is no longer active")
        memory = {"id": memory_id, "source_ref": row["source_ref"],
                  "content": row["content"], "summary": row["summary"]}
        form, rendered, count = _select_form(
            memory, used_tokens, request.budget_tokens, bool(context_parts)
        )
        if rendered:
            used_tokens += (_estimate_tokens("\n\n") if context_parts else 0) + count
            context_parts.append(rendered)
            items.append({"memory_id": memory_id, "selected_form": form, "token_count": count})
        else:
            excluded.append({"memory_id": memory_id, "reason_code": "BUDGET_EXCEEDED"})
    return {
        "requested_memory_ids": request.memory_ids,
        "included_memory_ids": [item["memory_id"] for item in items],
        "items": items, "excluded": excluded,
        "context_text": "\n\n".join(context_parts),
        "budget": {"limit_tokens": request.budget_tokens, "used_tokens": used_tokens,
                   "tokenizer": "utf8-bytes/3", "is_estimate": True},
    }


def handoff(data: MemoryHandoffInput | dict[str, Any]) -> dict[str, Any]:
    """Return a sourced summary of existing memories for a handoff objective."""
    request = data if isinstance(data, MemoryHandoffInput) else MemoryHandoffInput.model_validate(data)
    result = search_memories({
        "scope": request.scope, "query": request.objective,
        "mode": "hybrid" if embedding.enabled() else "keyword",
        "top_k": 20, "budget_tokens": request.budget_tokens,
        "filters": request.filters.model_dump(mode="json"),
    })
    return {
        "trace_id": result["trace_id"], "context_text": result["context_text"],
        "memory_ids": [item["memory"]["id"] for item in result["items"]],
        "budget": result["budget"],
    }


def search_memories(data: MemorySearchInput | dict[str, Any]) -> dict[str, Any]:
    request = data if isinstance(data, MemorySearchInput) else MemorySearchInput.model_validate(data)
    if request.mode != "keyword" and not embedding.enabled():
        raise EmbeddingUnavailable("vector and hybrid search require a configured embedding provider")
    started = perf_counter()
    filters = request.filters
    filters_json = filters.model_dump(mode="json")
    terms = _terms(request.query)
    if not terms:
        raise ValueError("query must contain searchable text")
    clauses = ["m.scope = %s", "m.status = 'active'",
               "(m.valid_from IS NULL OR m.valid_from <= UTC_TIMESTAMP(6))",
               "(m.valid_to IS NULL OR m.valid_to > UTC_TIMESTAMP(6))"]
    params: list[Any] = [request.scope]
    if filters.platforms is not None:
        placeholders = ", ".join(["%s"] * len(filters.platforms))
        clauses.append(f"m.source_platform IN ({placeholders})")
        params.extend(filters.platforms)
    if filters.conversation_ids is not None:
        placeholders = ", ".join(["%s"] * len(filters.conversation_ids))
        clauses.append(f"m.conversation_id IN ({placeholders})")
        params.extend(filters.conversation_ids)
    if filters.kinds is not None:
        placeholders = ", ".join(["%s"] * len(filters.kinds))
        clauses.append(f"m.kind IN ({placeholders})")
        params.extend(filters.kinds)
    for column, value, operator in (("created_at", filters.created_from, ">="),
                                    ("created_at", filters.created_to, "<=")):
        if value is not None:
            clauses.append(f"m.{column} {operator} %s")
            params.append(utc_database_time(value))
    base_where = " AND ".join(clauses)
    matches = ["(INSTR(LOWER(m.content), %s) > 0 OR "
               "INSTR(LOWER(COALESCE(m.summary, '')), %s) > 0)" for _ in terms]
    keyword_sql = (
        "SELECT m.* FROM memories m WHERE " + base_where + " AND ("
        + " OR ".join(matches) + ") ORDER BY m.created_at DESC, m.id DESC LIMIT 200"
    )
    vector_sql = (
        "SELECT m.*, L2_DISTANCE(m.embedding, %s) AS distance "
        "FROM memories m WHERE " + base_where + " AND m.embedding IS NOT NULL "
        "AND m.embedding_model = %s ORDER BY distance APPROXIMATE LIMIT 100"
    )
    with _transaction() as connection, connection.cursor() as cursor:
        if filters.conversation_ids:
            placeholders = ", ".join(["%s"] * len(filters.conversation_ids))
            cursor.execute(
                f"SELECT id FROM conversations WHERE scope = %s AND id IN ({placeholders})",
                (request.scope, *filters.conversation_ids),
            )
            if len(cursor.fetchall()) != len(filters.conversation_ids):
                raise NotFound("a conversation filter is outside this scope")
        keyword_rows: list[dict[str, Any]] = []
        vector_rows: list[dict[str, Any]] = []
        if request.mode in {"keyword", "hybrid"}:
            keyword_params = [*params, *(term for term in terms for _ in range(2))]
            cursor.execute(keyword_sql, keyword_params)
            keyword_rows = cursor.fetchall()
            keyword_rows.sort(key=lambda row: (
                -sum((row["content"] + " " + (row["summary"] or "")).lower().count(term)
                     for term in terms), -float(row["importance"]), -int(row["id"])
            ))
        if request.mode in {"vector", "hybrid"}:
            cursor.execute(
                vector_sql,
                (embedding.vector_json(request.query), *params, embedding.MODEL_ID),
            )
            vector_rows = cursor.fetchall()
        keyword_ranks = {str(row["id"]): rank for rank, row in enumerate(keyword_rows, 1)}
        vector_ranks = {str(row["id"]): rank for rank, row in enumerate(vector_rows, 1)}
        candidates = {str(row["id"]): row for row in [*keyword_rows, *vector_rows]}
        rows = sorted(candidates.values(), key=lambda row: (
            -(1 / (60 + keyword_ranks[str(row["id"])]) if str(row["id"]) in keyword_ranks else 0)
            -(1 / (60 + vector_ranks[str(row["id"])]) if str(row["id"]) in vector_ranks else 0),
            -float(row["importance"]), -int(row["id"]),
        ))
        memories = _with_links(cursor, rows[:request.top_k], request.scope)
        candidate_items: list[dict[str, Any]] = []
        context_parts: list[str] = []
        used_tokens = 0
        for rank, memory in enumerate(memories, 1):
            keyword_rank = keyword_ranks.get(memory["id"])
            vector_rank = vector_ranks.get(memory["id"])
            score = (1 / (60 + keyword_rank) if keyword_rank else 0) + (
                1 / (60 + vector_rank) if vector_rank else 0
            )
            form, rendered, count = _select_form(
                memory, used_tokens, request.budget_tokens, bool(context_parts)
            )
            if rendered:
                separator_tokens = _estimate_tokens("\n\n") if context_parts else 0
                context_parts.append(rendered)
                used_tokens += separator_tokens + count
            candidate_items.append({
                "memory": memory, "rank": rank,
                "channels": {"keyword_rank": keyword_rank, "vector_rank": vector_rank},
                "fusion_score": round(score, 6),
                "selected_form": form, "token_count": count,
                "reason_codes": (["KEYWORD_MATCH"] if keyword_rank else [])
                + (["VECTOR_MATCH"] if vector_rank else []) + (
                    ["BUDGET_SUMMARY"] if form == "summary" else
                    ["BUDGET_EXCEEDED"] if form is None else []),
            })
        items = [item for item in candidate_items if item["selected_form"] is not None]
        trace_items: list[dict[str, Any]] = list(candidate_items)
        for rank, row in enumerate(rows[request.top_k:], request.top_k + 1):
            key = str(row["id"])
            keyword_rank = keyword_ranks.get(key)
            vector_rank = vector_ranks.get(key)
            score = (1 / (60 + keyword_rank) if keyword_rank else 0) + (
                1 / (60 + vector_rank) if vector_rank else 0
            )
            trace_items.append({
                "memory": {"id": key}, "rank": rank,
                "channels": {"keyword_rank": keyword_rank, "vector_rank": vector_rank},
                "fusion_score": round(score, 6), "selected_form": None,
                "reason_codes": (["KEYWORD_MATCH"] if keyword_rank else [])
                + (["VECTOR_MATCH"] if vector_rank else []) + ["TOP_K_EXCEEDED"],
            })
        trace_id = str(uuid4())
        budget = {"limit_tokens": request.budget_tokens, "used_tokens": used_tokens,
                  "tokenizer": "utf8-bytes/3", "is_estimate": True}
        elapsed_ms = max(0, round((perf_counter() - started) * 1000))
        cursor.execute(
            "INSERT INTO retrieval_traces "
            "(trace_id, scope, query, mode_requested, mode_used, filters_applied, budget, "
            "candidate_count, selected_count, elapsed_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (trace_id, request.scope, request.query, request.mode, request.mode,
             json.dumps(filters_json, ensure_ascii=False), json.dumps(budget),
             len(rows), len(items), elapsed_ms),
        )
        for item in trace_items:
            cursor.execute(
                "INSERT INTO retrieval_trace_items "
                "(trace_id, memory_id, scope, fusion_rank, keyword_rank, vector_rank, "
                "fusion_score, decision, selected_form, reason_codes) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (trace_id, item["memory"]["id"], request.scope, item["rank"],
                 item["channels"]["keyword_rank"], item["channels"]["vector_rank"],
                 item["fusion_score"],
                 "selected" if item["selected_form"] else "excluded",
                 item["selected_form"], json.dumps(item["reason_codes"])),
            )
        return {
            "trace_id": trace_id, "scope": request.scope, "query": request.query,
            "mode_requested": request.mode, "mode_used": request.mode,
            "filters_applied": filters_json, "items": items,
            "context_text": "\n\n".join(context_parts), "budget": budget,
            "elapsed_ms": elapsed_ms,
        }
