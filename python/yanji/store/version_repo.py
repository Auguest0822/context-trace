"""Explicit memory replacement, history, and irreversible forgetting."""

from __future__ import annotations

import json
from typing import Any

from yanji import embedding
from yanji.models import MemoryReconcileInput, MemoryWriteInput, utc_database_time
from yanji.store.client import connect
from yanji.store.memory_repo import _memory, _selected_rows
from yanji.store.repo import (
    NotFound,
    StateConflict,
    _claim_request,
    _remember_response,
    _row_for_conversation,
    _transaction,
)


def _get(cursor: Any, scope: str, memory_id: str, *, lock: bool = False) -> dict[str, Any]:
    cursor.execute(
        "SELECT * FROM memories WHERE scope = %s AND id = %s" + (" FOR UPDATE" if lock else ""),
        (scope, memory_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise NotFound("memory not found in this scope")
    return row


def _render(cursor: Any, row: dict[str, Any], scope: str) -> dict[str, Any]:
    cursor.execute(
        "SELECT message_id FROM memory_message_links WHERE scope = %s AND memory_id = %s "
        "ORDER BY message_id", (scope, row["id"]),
    )
    return _memory(row, [str(item["message_id"]) for item in cursor.fetchall()])


def reconcile(data: MemoryReconcileInput | dict[str, Any]) -> dict[str, Any]:
    request = data if isinstance(data, MemoryReconcileInput) else MemoryReconcileInput.model_validate(data)
    replacement = MemoryWriteInput.model_validate({"scope": request.scope, **request.new_memory})
    body = request.model_dump(mode="json", exclude={"client_request_id"})
    with _transaction() as connection, connection.cursor() as cursor:
        cached = _claim_request(cursor, request.scope, str(request.client_request_id),
                                "memory_reconcile", body)
        if cached is not None:
            return cached
        old = _get(cursor, request.scope, request.old_memory_id, lock=True)
        if old["status"] != "active":
            raise StateConflict("only an active memory can be replaced")
        conversation = None
        message_ids = replacement.source_message_ids or []
        messages = {}
        source_ref = replacement.source_ref
        if replacement.source_type == "chat":
            assert replacement.conversation_id is not None
            conversation = _row_for_conversation(
                cursor, request.scope, replacement.conversation_id, lock=True
            )
            rows = _selected_rows(cursor, request.scope, replacement.conversation_id,
                                  message_ids)
            messages = {str(row["id"]): row for row in rows}
            if not any(replacement.source_excerpt in row["content"] for row in rows):
                raise ValueError("replacement source_excerpt is not in archived messages")
            source_ref = f"conversation:{conversation['id']}#message:{message_ids[0]}"
        cursor.execute(
            "INSERT INTO memories "
            "(scope, kind, content, summary, importance, source_type, source_ref, "
            "source_excerpt, source_platform, conversation_id, valid_from, valid_to) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (request.scope, replacement.kind, replacement.content, replacement.summary,
             replacement.importance, replacement.source_type, source_ref,
             replacement.source_excerpt,
             conversation["platform"] if conversation else None,
             conversation["id"] if conversation else None,
             utc_database_time(replacement.valid_from),
             utc_database_time(replacement.valid_to)),
        )
        new_id = cursor.lastrowid
        if embedding.enabled():
            cursor.execute(
                "UPDATE memories SET embedding = %s, embedding_model = %s, "
                "embedding_dim = %s WHERE id = %s AND scope = %s",
                (embedding.vector_json(replacement.content), embedding.MODEL_ID,
                 embedding.DIMENSION, new_id, request.scope),
            )
        for message_id in message_ids:
            text = messages[message_id]["content"]
            excerpt = (replacement.source_excerpt if replacement.source_excerpt in text
                       else text.strip()[:1000])
            cursor.execute(
                "INSERT INTO memory_message_links "
                "(memory_id, message_id, scope, source_excerpt) VALUES (%s, %s, %s, %s)",
                (new_id, message_id, request.scope, excerpt),
            )
        if conversation:
            cursor.execute(
                "UPDATE conversations SET memory_count = memory_count + 1 "
                "WHERE scope = %s AND id = %s", (request.scope, conversation["id"]),
            )
        cursor.execute(
            "UPDATE memories SET status = 'superseded', superseded_by = %s "
            "WHERE scope = %s AND id = %s", (new_id, request.scope, old["id"]),
        )
        cursor.execute(
            "INSERT INTO memory_revisions (old_memory_id, new_memory_id, scope, reason) "
            "VALUES (%s, %s, %s, %s)",
            (old["id"], new_id, request.scope, request.reason),
        )
        old = _get(cursor, request.scope, request.old_memory_id)
        new = _get(cursor, request.scope, str(new_id))
        result = {"old_memory": _render(cursor, old, request.scope),
                  "new_memory": _render(cursor, new, request.scope),
                  "reason": request.reason}
        _remember_response(cursor, request.scope, str(request.client_request_id), result)
        return result


def history(scope: str, memory_id: str) -> dict[str, Any]:
    with connect() as connection, connection.cursor() as cursor:
        _get(cursor, scope, memory_id)
        current = memory_id
        seen = set()
        while current not in seen:
            seen.add(current)
            cursor.execute(
                "SELECT old_memory_id FROM memory_revisions "
                "WHERE scope = %s AND new_memory_id = %s", (scope, current),
            )
            previous = cursor.fetchone()
            if previous is None:
                break
            current = str(previous["old_memory_id"])
        items = []
        seen.clear()
        while current not in seen:
            seen.add(current)
            row = _get(cursor, scope, current)
            cursor.execute(
                "SELECT new_memory_id, reason FROM memory_revisions "
                "WHERE scope = %s AND old_memory_id = %s", (scope, current),
            )
            revision = cursor.fetchone()
            items.append({"memory": _render(cursor, row, scope),
                          "superseded_by": str(row["superseded_by"]) if row["superseded_by"] else None,
                          "reason": revision["reason"] if revision else None})
            if revision is None:
                break
            current = str(revision["new_memory_id"])
        return {"items": items}


def _contains_memory(value: Any, scope: str, memory_id: str) -> bool:
    if isinstance(value, dict):
        if (str(value.get("id")) == memory_id and value.get("scope") == scope
                and "source_ref" in value):
            return True
        return any(_contains_memory(item, scope, memory_id) for item in value.values())
    if isinstance(value, list):
        return any(_contains_memory(item, scope, memory_id) for item in value)
    return False


def forget(scope: str, memory_id: str) -> dict[str, Any]:
    with _transaction() as connection, connection.cursor() as cursor:
        row = _get(cursor, scope, memory_id, lock=True)
        cursor.execute(
            "UPDATE memories SET superseded_by = %s, "
            "status = CASE WHEN %s IS NULL THEN 'expired' ELSE 'superseded' END "
            "WHERE scope = %s AND superseded_by = %s",
            (row["superseded_by"], row["superseded_by"], scope, row["id"]),
        )
        cursor.execute(
            "SELECT client_request_id, response_json FROM idempotency_requests "
            "WHERE scope = %s AND response_json IS NOT NULL", (scope,),
        )
        for cached in cursor.fetchall():
            response = cached["response_json"]
            value = json.loads(response) if isinstance(response, str) else response
            if _contains_memory(value, scope, memory_id):
                cursor.execute(
                    "DELETE FROM idempotency_requests WHERE scope = %s AND client_request_id = %s",
                    (scope, cached["client_request_id"]),
                )
        cursor.execute("DELETE FROM retrieval_trace_items WHERE scope = %s AND memory_id = %s",
                       (scope, row["id"]))
        cursor.execute(
            "SELECT old_memory_id, reason FROM memory_revisions "
            "WHERE scope = %s AND new_memory_id = %s", (scope, row["id"]),
        )
        previous = cursor.fetchone()
        if previous and row["superseded_by"] is not None:
            cursor.execute(
                "UPDATE memory_revisions SET new_memory_id = %s "
                "WHERE scope = %s AND old_memory_id = %s",
                (row["superseded_by"], scope, previous["old_memory_id"]),
            )
            cursor.execute(
                "DELETE FROM memory_revisions WHERE scope = %s AND old_memory_id = %s",
                (scope, row["id"]),
            )
        else:
            cursor.execute(
                "DELETE FROM memory_revisions WHERE scope = %s "
                "AND (old_memory_id = %s OR new_memory_id = %s)",
                (scope, row["id"], row["id"]),
            )
        cursor.execute("DELETE FROM memory_message_links WHERE scope = %s AND memory_id = %s",
                       (scope, row["id"]))
        cursor.execute("DELETE FROM memories WHERE scope = %s AND id = %s",
                       (scope, row["id"]))
        if row["conversation_id"] is not None:
            cursor.execute(
                "UPDATE conversations SET memory_count = GREATEST(memory_count - 1, 0) "
                "WHERE scope = %s AND id = %s", (scope, row["conversation_id"]),
            )
        return {"deleted": True, "memory_id": memory_id}
