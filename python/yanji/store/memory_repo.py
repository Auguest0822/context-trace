"""Manual memory previews and confirmed chat-memory writes.

Manual drafts are literal excerpts from archived messages. They are not AI output;
the user must edit and explicitly confirm them. Vector generation is a later phase.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from yanji.models import ExtractionCommitInput, ExtractionPreviewInput
from yanji.store.client import connect
from yanji.store.repo import (
    NotFound, StateConflict, _claim_request, _remember_response, _row_for_conversation,
    _timestamp, _transaction,
)


class PreviewExpired(Exception):
    """The 24-hour review window has passed."""


def _json(value: str | list[Any]) -> list[Any]:
    return json.loads(value) if isinstance(value, str) else value


def _selected_rows(cursor: Any, scope: str, conversation_id: str | int,
                   message_ids: list[str]) -> list[dict[str, Any]]:
    placeholders = ", ".join(["%s"] * len(message_ids))
    cursor.execute(
        "SELECT * FROM messages WHERE scope = %s AND conversation_id = %s "
        f"AND id IN ({placeholders}) ORDER BY sequence ASC, id ASC",
        (scope, conversation_id, *message_ids),
    )
    rows = cursor.fetchall()
    if len(rows) != len(message_ids):
        raise NotFound("selected messages were not found in this conversation and scope")
    return rows


def _check_evidence(candidate: dict[str, Any], selected_ids: set[str],
                    messages: dict[str, dict[str, Any]]) -> None:
    ids = candidate.get("source_message_ids")
    excerpt = candidate.get("source_excerpt")
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ValueError("candidate must cite distinct archived messages")
    if not set(ids) <= selected_ids or not set(ids) <= messages.keys():
        raise ValueError("candidate cites a message outside the selected conversation")
    if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 1000:
        raise ValueError("candidate source_excerpt is invalid")
    if not any(excerpt in messages[message_id]["content"] for message_id in ids):
        raise ValueError("candidate source_excerpt is not in its cited archived messages")


def _memory(row: dict[str, Any], message_ids: list[str]) -> dict[str, Any]:
    return {
        "id": str(row["id"]), "scope": row["scope"], "kind": row["kind"],
        "content": row["content"], "summary": row["summary"],
        "importance": row["importance"], "status": row["status"],
        "superseded_by": str(row["superseded_by"]) if row["superseded_by"] else None,
        "source_type": row["source_type"], "source_ref": row["source_ref"],
        "source_excerpt": row["source_excerpt"], "source_platform": row["source_platform"],
        "conversation_id": str(row["conversation_id"]),
        "source_message_ids": message_ids,
        "valid_from": _timestamp(row["valid_from"]),
        "valid_to": _timestamp(row["valid_to"]),
        "created_at": _timestamp(row["created_at"]),
        "updated_at": _timestamp(row["updated_at"]),
    }


def get_memory(scope: str, memory_id: str) -> dict[str, Any]:
    """Read a confirmed memory with its archived message references."""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM memories WHERE id = %s AND scope = %s",
                           (memory_id, scope))
            row = cursor.fetchone()
            if row is None:
                raise NotFound("memory not found in this scope")
            cursor.execute(
                "SELECT message_id FROM memory_message_links "
                "WHERE memory_id = %s AND scope = %s ORDER BY message_id ASC",
                (memory_id, scope),
            )
            ids = [str(item["message_id"]) for item in cursor.fetchall()]
            return _memory(row, ids)


def create_manual_preview(data: ExtractionPreviewInput | dict[str, Any]) -> dict[str, Any]:
    request = (data if isinstance(data, ExtractionPreviewInput)
               else ExtractionPreviewInput.model_validate(data))
    preview_id = str(uuid4())
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
    with _transaction() as connection:
        with connection.cursor() as cursor:
            _row_for_conversation(cursor, request.scope, request.conversation_id)
            rows = _selected_rows(cursor, request.scope, request.conversation_id,
                                  request.message_ids)
            candidates = []
            for row in rows:
                # A literal draft is safe to display without a model. The user edits it.
                excerpt = row["content"].strip()[:1000]
                candidates.append({
                    "candidate_id": str(uuid4()), "kind": "fact", "content": excerpt,
                    "summary": None, "source_message_ids": [str(row["id"])],
                    "source_excerpt": excerpt,
                })
            selected_ids = [str(row["id"]) for row in rows]
            cursor.execute(
                "INSERT INTO extraction_previews "
                "(id, scope, conversation_id, selected_message_ids, candidates, status, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, 'pending', %s)",
                (preview_id, request.scope, request.conversation_id,
                 json.dumps(selected_ids), json.dumps(candidates, ensure_ascii=False), expires),
            )
    return {
        "preview_id": preview_id, "expires_at": _timestamp(expires),
        "conversation_id": request.conversation_id,
        "selected_message_ids": selected_ids, "candidates": candidates,
    }


def commit_manual_preview(preview_id: str, data: ExtractionCommitInput | dict[str, Any]
                          ) -> dict[str, Any]:
    request = (data if isinstance(data, ExtractionCommitInput)
               else ExtractionCommitInput.model_validate(data))
    body = request.model_dump(mode="json", exclude={"client_request_id"})
    body["preview_id"] = preview_id
    with _transaction() as connection:
        with connection.cursor() as cursor:
            cached = _claim_request(cursor, request.scope, str(request.client_request_id),
                                    "commit_preview", body)
            if cached is not None:
                return cached
            cursor.execute(
                "SELECT * FROM extraction_previews WHERE id = %s AND scope = %s FOR UPDATE",
                (preview_id, request.scope),
            )
            preview = cursor.fetchone()
            if preview is None:
                raise NotFound("preview not found in this scope")
            if preview["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None):
                raise PreviewExpired("preview expired; generate a new one")
            if preview["status"] != "pending":
                raise StateConflict("preview has already been committed")
            candidates = {item["candidate_id"]: item for item in _json(preview["candidates"])}
            chosen = []
            for item in request.selected:
                candidate = candidates.get(str(item.candidate_id))
                if candidate is None:
                    raise ValueError("candidate_id does not belong to this preview")
                chosen.append((item, candidate))

            memories = []
            if chosen:
                conversation = _row_for_conversation(
                    cursor, request.scope, preview["conversation_id"], lock=True
                )
                selected_ids = set(_json(preview["selected_message_ids"]))
                cited_ids = list({mid for _, candidate in chosen
                                  for mid in candidate["source_message_ids"]})
                if not cited_ids:
                    raise ValueError("candidate must cite an archived message")
                rows = _selected_rows(cursor, request.scope, preview["conversation_id"],
                                      cited_ids)
                messages = {str(row["id"]): row for row in rows}
                for item, candidate in chosen:
                    _check_evidence(candidate, selected_ids, messages)
                    source_ids = candidate["source_message_ids"]
                    cursor.execute(
                        "INSERT INTO memories "
                        "(scope, kind, content, summary, source_type, source_ref, source_excerpt, "
                        "source_platform, conversation_id) VALUES (%s, %s, %s, %s, 'chat', %s, "
                        "%s, %s, %s)",
                        (request.scope, item.kind, item.content, item.summary,
                         f"conversation:{conversation['id']}#message:{source_ids[0]}",
                         candidate["source_excerpt"], conversation["platform"],
                         conversation["id"]),
                    )
                    memory_id = cursor.lastrowid
                    for message_id in source_ids:
                        message_text = messages[message_id]["content"]
                        link_excerpt = (candidate["source_excerpt"] if
                                        candidate["source_excerpt"] in message_text else
                                        message_text.strip()[:1000])
                        cursor.execute(
                            "INSERT INTO memory_message_links "
                            "(memory_id, message_id, scope, source_excerpt) "
                            "VALUES (%s, %s, %s, %s)",
                            (memory_id, message_id, request.scope, link_excerpt),
                        )
                    cursor.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
                    memories.append(_memory(cursor.fetchone(), source_ids))
                cursor.execute(
                    "UPDATE conversations SET memory_count = memory_count + %s, "
                    "updated_at = UTC_TIMESTAMP(6) WHERE id = %s AND scope = %s",
                    (len(memories), conversation["id"], request.scope),
                )
            cursor.execute(
                "UPDATE extraction_previews SET status = 'committed', "
                "committed_at = UTC_TIMESTAMP(6) WHERE id = %s AND scope = %s",
                (preview_id, request.scope),
            )
            result = {"memories": memories, "created": bool(memories)}
            _remember_response(cursor, request.scope, str(request.client_request_id), result)
            return result
