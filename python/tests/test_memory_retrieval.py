"""D5 acceptance boundaries that do not require a running seekdb process."""

import os
import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from pydantic import ValidationError
from yanji.models import MemorySearchInput, MemoryWriteInput
from yanji.store import retrieval


class FakeCursor:
    def __init__(self):
        self.sql = []
        self.active = []
        self.at = datetime(2026, 10, 11)

    def __enter__(self): return self
    def __exit__(self, *_): return False

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        if sql.startswith("SELECT m.*, L2_DISTANCE"):
            self.active = [{
                "id": 102, "scope": "project:test", "kind": "fact",
                "content": "另一条向量候选", "summary": None,
                "importance": 0.5, "status": "active", "superseded_by": None,
                "source_type": "chat", "source_ref": "conversation:201#message:302",
                "source_excerpt": "另一条向量候选", "source_platform": "deepseek",
                "conversation_id": 201, "valid_from": None, "valid_to": None,
                "created_at": self.at, "updated_at": self.at, "distance": 0.1,
            }]
        elif sql.startswith("SELECT m.*"):
            self.active = [{
                "id": 101, "scope": "project:test", "kind": "decision",
                "content": "初赛优先保证仓库可复现", "summary": "优先仓库可复现",
                "importance": 0.8, "status": "active", "superseded_by": None,
                "source_type": "chat", "source_ref": "conversation:201#message:301",
                "source_excerpt": "初赛要以仓库可复现为优先", "source_platform": "deepseek",
                "conversation_id": 201, "valid_from": None, "valid_to": None,
                "created_at": self.at, "updated_at": self.at,
            }]
        elif sql.startswith("SELECT memory_id"):
            self.active = [{"memory_id": 101, "message_id": 301},
                           {"memory_id": 102, "message_id": 302}]
        elif sql.startswith("SELECT id FROM conversations"):
            self.active = [{"id": 201}]
        else:
            self.active = []

    def fetchall(self): return self.active


class FakeConnection:
    def __init__(self): self.db = FakeCursor()
    def cursor(self): return self.db


@contextmanager
def fake_transaction():
    yield FakeConnection()


class MemoryRetrievalTests(unittest.TestCase):
    def test_context_uses_only_selected_ids_and_preserves_source(self):
        self.assertEqual(retrieval.assemble_context({
            "scope": "project:test", "memory_ids": [], "budget_tokens": 100,
        })["context_text"], "")
        class ContextCursor:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def execute(self, sql, params):
                self.params = params
            def fetchall(self):
                return [{"id": 101, "status": "active", "valid_from": None,
                         "valid_to": None, "source_ref": "docs/repro.md", "content": "记忆正文",
                         "summary": "摘要"}]
        class ContextConnection:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def cursor(self): return ContextCursor()
        with patch.object(retrieval, "connect", return_value=ContextConnection()):
            result = retrieval.assemble_context({
                "scope": "project:test", "memory_ids": ["101"], "budget_tokens": 100,
            })
        self.assertEqual(result["included_memory_ids"], ["101"])
        self.assertIn("source:docs/repro.md", result["context_text"])
        self.assertEqual(result["requested_memory_ids"], ["101"])

    def test_search_input_rejects_ambiguous_filters(self):
        with self.assertRaises(ValidationError):
            MemorySearchInput(scope="x", query="部署", mode="keyword",
                              filters={"platforms": []})
        with self.assertRaises(ValidationError):
            MemorySearchInput(scope="x", query="部署", mode="keyword",
                              filters={"kinds": ["decision", "decision"]})
        with self.assertRaises(ValidationError):
            MemoryWriteInput(scope="x", kind="decision", content="结论",
                             source_type="chat", source_ref="invented", source_excerpt="依据",
                             conversation_id="1", source_message_ids=["2"])

    def test_vector_mode_does_not_silently_fallback(self):
        with self.assertRaises(retrieval.EmbeddingUnavailable):
            retrieval.search_memories({"scope": "project:test", "query": "初赛"})

    def test_keyword_result_keeps_scope_source_budget_and_trace(self):
        connection = FakeConnection()
        @contextmanager
        def transaction():
            yield connection
        with patch.object(retrieval, "_transaction", transaction):
            result = retrieval.search_memories({
                "scope": "project:test", "query": "初赛可复现", "mode": "keyword",
                "filters": {"platforms": ["deepseek"], "conversation_ids": ["201"]},
            })
        self.assertEqual(result["mode_used"], "keyword")
        self.assertEqual(result["items"][0]["memory"]["source_message_ids"], ["301"])
        self.assertIn("source:conversation:201#message:301", result["context_text"])
        self.assertLessEqual(result["budget"]["used_tokens"], result["budget"]["limit_tokens"])
        select_sql, params = next((sql, p) for sql, p in connection.db.sql
                                  if sql.startswith("SELECT m.*"))
        self.assertIn("m.scope = %s", select_sql)
        self.assertIn("m.status = 'active'", select_sql)
        self.assertIn("m.source_platform IN", select_sql)
        self.assertIn("project:test", params)
        self.assertTrue(any(sql.startswith("INSERT INTO retrieval_traces")
                            for sql, _ in connection.db.sql))

    def test_hybrid_includes_vector_only_candidate_without_keyword_gate(self):
        connection = FakeConnection()
        @contextmanager
        def transaction():
            yield connection
        with (
            patch.dict(os.environ, {"YANJI_EMBEDDING_BACKEND": "hash"}),
            patch.object(retrieval, "_transaction", transaction),
        ):
            result = retrieval.search_memories({
                "scope": "project:test", "query": "初赛", "mode": "hybrid", "top_k": 2,
            })
        ids = {item["memory"]["id"] for item in result["items"]}
        self.assertEqual(ids, {"101", "102"})
        vector_only = next(item for item in result["items"] if item["memory"]["id"] == "102")
        self.assertIsNone(vector_only["channels"]["keyword_rank"])
        self.assertEqual(vector_only["channels"]["vector_rank"], 1)
        vector_sql = next(sql for sql, _ in connection.db.sql if "L2_DISTANCE" in sql)
        self.assertNotIn("INSTR", vector_sql)


if __name__ == "__main__":
    unittest.main()
