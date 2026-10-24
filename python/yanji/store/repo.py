"""Conversation archive persistence; no extraction or memory writes happen here."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from yanji.config import SeekDBSettings
from yanji.models import ConversationInput, MessageAppendInput, MessageInput, utc_database_time
from yanji.store.client import connect


class NotFound(LookupError):
    """The requested row does not exist in this scope."""


class StateConflict(ValueError):
    """An imported message disagrees with an existing archived message."""


class IdempotencyConflict(StateConflict):
    """A client_request_id was reused for a different operation or body."""


@contextmanager
def _transaction(settings: SeekDBSettings | None = None) -> Iterator[Connection]:
    connection = connect(settings)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _conversation(row: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "scope", "platform", "external_conversation_id", "title", "source_url",
        "capture_method", "capture_completeness", "message_count", "memory_count",
    )
    result = {field: row[field] for field in fields}
    result["id"] = str(row["id"])
    for field in ("captured_at", "created_at", "updated_at"):
        result[field] = _timestamp(row[field])
    return result


def _message(row: dict[str, Any]) -> dict[str, Any]:
    fields = ("scope", "external_message_id", "sequence", "role", "content")
    result = {field: row[field] for field in fields}
    result["id"] = str(row["id"])
    result["conversation_id"] = str(row["conversation_id"])
    result["sent_at"] = _timestamp(row["sent_at"])
    result["captured_at"] = _timestamp(row["captured_at"])
    return result


def _row_for_conversation(
    cursor: DictCursor, scope: str, conversation_id: str | int, *, lock: bool = False
) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        "SELECT * FROM conversations WHERE scope = %s AND id = %s" + suffix,
        (scope, conversation_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise NotFound("conversation not found in this scope")
    return row


def _request_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim_request(
    cursor: DictCursor, scope: str, request_id: str | None, operation: str, body: dict[str, Any]
) -> dict[str, Any] | None:
    if request_id is None:
        return None
    digest = _request_hash(body)
    cursor.execute(
        "INSERT INTO idempotency_requests "
        "(scope, client_request_id, operation, request_hash) VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE client_request_id = client_request_id",
        (scope, request_id, operation, digest),
    )
    cursor.execute(
        "SELECT operation, request_hash, response_json FROM idempotency_requests "
        "WHERE scope = %s AND client_request_id = %s FOR UPDATE",
        (scope, request_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise StateConflict("idempotency request was not persisted")
    if row["operation"] != operation or row["request_hash"] != digest:
        raise IdempotencyConflict("client_request_id already belongs to another request")
    if row["response_json"] is not None:
        return json.loads(row["response_json"])
    return None


def _remember_response(
    cursor: DictCursor, scope: str, request_id: str | None, result: dict[str, Any]
) -> None:
    if request_id is not None:
        cursor.execute(
            "UPDATE idempotency_requests SET response_json = %s "
            "WHERE scope = %s AND client_request_id = %s",
            (json.dumps(result, ensure_ascii=False), scope, request_id),
        )


def _store_messages(
    cursor: DictCursor, scope: str, conversation_id: int, messages: list[MessageInput]
) -> tuple[list[dict[str, Any]], int]:
    stored: list[dict[str, Any]] = []
    inserted = 0
    for message in messages:
        cursor.execute(
            "SELECT * FROM messages WHERE conversation_id = %s AND sequence = %s FOR UPDATE",
            (conversation_id, message.sequence),
        )
        by_sequence = cursor.fetchone()
        by_external = None
        if message.external_message_id is not None:
            cursor.execute(
                "SELECT * FROM messages WHERE conversation_id = %s "
                "AND external_message_id = %s FOR UPDATE",
                (conversation_id, message.external_message_id),
            )
            by_external = cursor.fetchone()
        if by_sequence and by_external and by_sequence["id"] != by_external["id"]:
            raise StateConflict("sequence and external_message_id identify different messages")
        existing = by_sequence or by_external
        if existing is not None:
            if (
                existing["sequence"] != message.sequence
                or existing["role"] != message.role
                or existing["content"] != message.content
                or (
                    existing["external_message_id"] is not None
                    and message.external_message_id is not None
                    and existing["external_message_id"] != message.external_message_id
                )
            ):
                raise StateConflict("archived message differs from imported message")
            if existing["external_message_id"] is None and message.external_message_id is not None:
                cursor.execute(
                    "UPDATE messages SET external_message_id = %s WHERE id = %s",
                    (message.external_message_id, existing["id"]),
                )
                existing["external_message_id"] = message.external_message_id
            stored.append(_message(existing))
            continue
        cursor.execute(
            "INSERT INTO messages (conversation_id, scope, external_message_id, sequence, "
            "role, content, content_sha256, sent_at, captured_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(6))",
            (
                conversation_id, scope, message.external_message_id, message.sequence,
                message.role, message.content,
                hashlib.sha256(message.content.encode("utf-8")).hexdigest(),
                utc_database_time(message.sent_at),
            ),
        )
        message_id = cursor.lastrowid
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        stored.append(_message(cursor.fetchone()))
        inserted += 1
    if inserted:
        cursor.execute(
            "UPDATE conversations SET message_count = message_count + %s, "
            "updated_at = UTC_TIMESTAMP(6) WHERE id = %s AND scope = %s",
            (inserted, conversation_id, scope),
        )
    return stored, inserted


def capture_conversation(
    data: ConversationInput | dict[str, Any], settings: SeekDBSettings | None = None
) -> dict[str, Any]:
    """Archive selected messages atomically; repeated imports merge without duplicates."""
    request = (
        data if isinstance(data, ConversationInput) else ConversationInput.model_validate(data)
    )
    request_id = str(request.client_request_id) if request.client_request_id else None
    body = request.model_dump(mode="json", exclude={"client_request_id"})
    with _transaction(settings) as connection, connection.cursor() as cursor:
        cached = _claim_request(cursor, request.scope, request_id, "capture", body)
        if cached is not None:
            return cached
        existing = None
        if request.external_conversation_id is not None:
            cursor.execute(
                "SELECT * FROM conversations WHERE scope = %s AND platform = %s "
                "AND external_conversation_id = %s FOR UPDATE",
                (request.scope, request.platform, request.external_conversation_id),
            )
            existing = cursor.fetchone()
        created = existing is None
        if created:
            cursor.execute(
                "INSERT INTO conversations (scope, platform, external_conversation_id, "
                "title, source_url, capture_method, capture_completeness, captured_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(6))",
                (
                    request.scope, request.platform, request.external_conversation_id,
                    request.title, request.source_url, request.capture_method,
                    request.capture_completeness,
                ),
            )
            conversation_id = cursor.lastrowid
        else:
            assert existing is not None
            conversation_id = existing["id"]
        stored, inserted = _store_messages(
            cursor, request.scope, conversation_id, request.messages
        )
        row = _row_for_conversation(cursor, request.scope, conversation_id)
        result = {
            "conversation": _conversation(row),
            "messages": stored,
            "inserted_count": inserted,
            "created": created,  # Used by the future HTTP route to select 201 or 200.
        }
        _remember_response(cursor, request.scope, request_id, result)
        return result


def append_messages(
    conversation_id: str | int,
    data: MessageAppendInput | dict[str, Any],
    settings: SeekDBSettings | None = None,
) -> dict[str, Any]:
    """Append or deduplicate selected messages in one existing conversation."""
    request = (
        data if isinstance(data, MessageAppendInput) else MessageAppendInput.model_validate(data)
    )
    request_id = str(request.client_request_id) if request.client_request_id else None
    body = request.model_dump(mode="json", exclude={"client_request_id"})
    body["conversation_id"] = str(conversation_id)
    with _transaction(settings) as connection, connection.cursor() as cursor:
        cached = _claim_request(cursor, request.scope, request_id, "append", body)
        if cached is not None:
            return cached
        row = _row_for_conversation(cursor, request.scope, conversation_id, lock=True)
        stored, inserted = _store_messages(cursor, request.scope, row["id"], request.messages)
        result = {
            "conversation": _conversation(
                _row_for_conversation(cursor, request.scope, conversation_id)
            ),
            "messages": stored,
            "inserted_count": inserted,
        }
        _remember_response(cursor, request.scope, request_id, result)
        return result


def get_conversation(
    scope: str, conversation_id: str | int, settings: SeekDBSettings | None = None
) -> dict[str, Any]:
    with connect(settings) as connection, connection.cursor() as cursor:
        return _conversation(_row_for_conversation(cursor, scope, conversation_id))


def _encode_cursor(*parts: Any) -> str:
    value = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_cursor(value: str, expected_length: int) -> list[Any]:
    try:
        padded = value + "=" * (-len(value) % 4)
        parts = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(parts, list) or len(parts) != expected_length:
            raise ValueError
        return parts
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError("invalid pagination cursor") from exc


def list_conversations(
    scope: str,
    *,
    platform: str | None = None,
    q: str | None = None,
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
    limit: int = 20,
    cursor: str | None = None,
    settings: SeekDBSettings | None = None,
) -> dict[str, Any]:
    """List one page in a scope, newest updated conversation first."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if q is not None and not 1 <= len(q) <= 100:
        raise ValueError("q must contain 1 to 100 characters")
    from_utc, to_utc = utc_database_time(captured_from), utc_database_time(captured_to)
    if from_utc and to_utc and from_utc > to_utc:
        raise ValueError("captured_from cannot be later than captured_to")
    filter_key = _request_hash({
        "platform": platform, "q": q,
        "captured_from": _timestamp(from_utc), "captured_to": _timestamp(to_utc),
    })
    clauses = ["scope = %s"]
    params: list[Any] = [scope]
    if platform is not None:
        clauses.append("platform = %s")
        params.append(platform)
    if q is not None:
        clauses.append("INSTR(title, %s) > 0")
        params.append(q)
    if from_utc is not None:
        clauses.append("captured_at >= %s")
        params.append(from_utc)
    if to_utc is not None:
        clauses.append("captured_at <= %s")
        params.append(to_utc)
    if cursor is not None:
        cursor_scope, cursor_filters, updated, last_id = _decode_cursor(cursor, 4)
        if cursor_scope != scope or cursor_filters != filter_key:
            raise ValueError("cursor does not match the requested scope and filters")
        clauses.append("(updated_at < %s OR (updated_at = %s AND id < %s))")
        params.extend([updated, updated, last_id])
    sql = (
        "SELECT * FROM conversations WHERE " + " AND ".join(clauses)
        + " ORDER BY updated_at DESC, id DESC LIMIT %s"
    )
    with connect(settings) as connection, connection.cursor() as db_cursor:
        db_cursor.execute(sql, (*params, limit + 1))
        rows = db_cursor.fetchall()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(
            scope, filter_key, last["updated_at"].isoformat(sep=" "), last["id"]
        )
    return {"items": [_conversation(row) for row in page], "next_cursor": next_cursor}


def list_messages(
    scope: str,
    conversation_id: str | int,
    *,
    limit: int = 50,
    cursor: str | None = None,
    settings: SeekDBSettings | None = None,
) -> dict[str, Any]:
    """List messages by their original sequence, never by insertion time."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    clauses = ["scope = %s", "conversation_id = %s"]
    params: list[Any] = [scope, conversation_id]
    if cursor is not None:
        cursor_scope, cursor_conversation, sequence, last_id = _decode_cursor(cursor, 4)
        if cursor_scope != scope or cursor_conversation != str(conversation_id):
            raise ValueError("cursor does not match the requested conversation")
        clauses.append("(sequence > %s OR (sequence = %s AND id > %s))")
        params.extend([sequence, sequence, last_id])
    sql = (
        "SELECT * FROM messages WHERE " + " AND ".join(clauses)
        + " ORDER BY sequence ASC, id ASC LIMIT %s"
    )
    with connect(settings) as connection, connection.cursor() as db_cursor:
        _row_for_conversation(db_cursor, scope, conversation_id)
        db_cursor.execute(sql, (*params, limit + 1))
        rows = db_cursor.fetchall()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_cursor(scope, str(conversation_id), last["sequence"], last["id"])
    return {"items": [_message(row) for row in page], "next_cursor": next_cursor}
