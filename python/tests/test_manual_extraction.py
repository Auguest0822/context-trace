"""Manual preview contract and exact archived-message evidence checks."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4
from json import loads

from pydantic import ValidationError
from starlette.requests import Request

from yanji.models import ExtractionCommitInput, ExtractionPreviewInput
from yanji.server.api import commit_extraction, get_memory, preview_extraction
from yanji.store.memory_repo import _check_evidence, commit_manual_preview, create_manual_preview


class MemoryCursor:
    """Small transactional seekdb stand-in for the preview/confirm boundary."""

    def __init__(self) -> None:
        self.queries = []
        self.preview = None
        self.lastrowid = 401
        self.result = None
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        if sql.startswith("SELECT * FROM conversations"):
            self.result = {"id": 201, "platform": "deepseek"}
        elif sql.startswith("SELECT * FROM messages"):
            self.result = [{"id": 301, "content": "初赛要以仓库可复现为优先。", "sequence": 1}]
        elif sql.startswith("INSERT INTO extraction_previews"):
            self.preview = {"id": params[0], "scope": params[1], "conversation_id": 201,
                            "selected_message_ids": params[3], "candidates": params[4],
                            "status": "pending", "expires_at": params[5]}
        elif sql.startswith("SELECT operation, request_hash"):
            operation = next(params[2] for sql, params in self.queries
                             if sql.startswith("INSERT INTO idempotency_requests"))
            self.result = {"operation": operation, "request_hash": self.queries[-2][1][3],
                           "response_json": None}
        elif sql.startswith("SELECT * FROM extraction_previews"):
            self.result = self.preview
        elif sql.startswith("SELECT * FROM memories"):
            self.result = {"id": 401, "scope": "project:x", "kind": "decision",
                           "content": "优先保证仓库可复现", "summary": None,
                           "importance": 0.5, "status": "active", "superseded_by": None,
                           "source_type": "chat", "source_ref": "conversation:201#message:301",
                           "source_excerpt": "初赛要以仓库可复现为优先。",
                           "source_platform": "deepseek", "conversation_id": 201,
                           "valid_from": None, "valid_to": None,
                           "created_at": self.now, "updated_at": self.now}

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


class MemoryConnection:
    def __init__(self):
        self.cursor_instance = MemoryCursor()

    def cursor(self):
        return self.cursor_instance


@contextmanager
def fake_transaction(connection):
    yield connection


class ManualExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview_id = str(uuid4())
        self.candidate_id = str(uuid4())
        self.request = Request({"type": "http", "method": "POST", "path": "/",
                                "query_string": b"", "headers": []})

    def test_preview_requires_one_conversation_and_unique_message_ids(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractionPreviewInput(scope="project:x", conversation_id="201",
                                   message_ids=["301", "301"])
        with self.assertRaises(ValidationError):
            ExtractionPreviewInput(scope="project:x", conversation_id="201",
                                   message_ids=["301"], mode="automatic")
        with self.assertRaises(ValidationError):
            ExtractionPreviewInput(scope="project:x", conversation_id="201", message_ids=[])

    def test_evidence_must_be_literal_text_in_selected_archived_message(self) -> None:
        message = {"301": {"content": "初赛要以仓库可复现为优先。"}}
        candidate = {"source_message_ids": ["301"], "source_excerpt": "仓库可复现"}
        _check_evidence(candidate, {"301"}, message)
        with self.assertRaisesRegex(ValueError, "not in"):
            _check_evidence({**candidate, "source_excerpt": "未说过的结论"}, {"301"}, message)
        with self.assertRaisesRegex(ValueError, "outside"):
            _check_evidence(candidate, {"302"}, message)

    def test_preview_commit_and_read_routes_preserve_contract(self) -> None:
        preview = {
            "preview_id": self.preview_id, "conversation_id": "201",
            "selected_message_ids": ["301"], "expires_at": "2026-10-16T00:00:00Z",
            "candidates": [{"candidate_id": self.candidate_id, "kind": "fact",
                            "content": "仓库可复现", "summary": None,
                            "source_message_ids": ["301"], "source_excerpt": "仓库可复现"}],
        }
        request = ExtractionPreviewInput(scope="project:x", conversation_id="201",
                                         message_ids=["301"], mode="manual")
        with patch("yanji.server.api.memory_repo.create_manual_preview", return_value=preview) as save:
            result = preview_extraction(self.request, request)
        self.assertEqual(result, preview)
        self.assertEqual(save.call_args.args[0].message_ids, ["301"])

        payload = {"scope": "project:x", "client_request_id": str(uuid4()),
                   "selected": [{"candidate_id": self.candidate_id, "kind": "decision",
                                 "content": "优先保证仓库可复现", "summary": None}]}
        data = ExtractionCommitInput.model_validate(payload)
        memory = {"id": "401", "source_message_ids": ["301"],
                  "source_excerpt": "仓库可复现"}
        with patch("yanji.server.api.memory_repo.commit_manual_preview",
                   return_value={"memories": [memory], "created": True}) as save:
            response = commit_extraction(self.request, self.preview_id, data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(loads(response.body), {"memories": [memory]})
        self.assertEqual(str(save.call_args.args[1].selected[0].candidate_id), self.candidate_id)

        with patch("yanji.server.api.memory_repo.get_memory", return_value=memory):
            result = get_memory(self.request, "401", "project:x")
        self.assertEqual(result["memory"], memory)

    def test_storage_keeps_preview_separate_then_writes_checked_evidence(self) -> None:
        connection = MemoryConnection()
        with patch("yanji.store.memory_repo._transaction",
                   side_effect=lambda: fake_transaction(connection)):
            preview = create_manual_preview({"scope": "project:x", "conversation_id": "201",
                                             "message_ids": ["301"], "mode": "manual"})
            self.assertEqual(preview["candidates"][0]["source_excerpt"],
                             "初赛要以仓库可复现为优先。")
            self.assertFalse(any("INSERT INTO memories" in query for query, _ in
                                 connection.cursor_instance.queries))
            result = commit_manual_preview(preview["preview_id"], {
                "scope": "project:x", "client_request_id": str(uuid4()),
                "selected": [{"candidate_id": preview["candidates"][0]["candidate_id"],
                              "kind": "decision", "content": "优先保证仓库可复现",
                              "summary": None}],
            })
        self.assertEqual(result["memories"][0]["source_message_ids"], ["301"])
        self.assertEqual(result["memories"][0]["source_ref"], "conversation:201#message:301")
        self.assertTrue(any("INSERT INTO memory_message_links" in query for query, _ in
                            connection.cursor_instance.queries))


if __name__ == "__main__":
    unittest.main()
