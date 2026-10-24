"""Replacement must be explicit, sourced, and one atomic transaction."""

import unittest
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError
from yanji.models import MemoryReconcileInput
from yanji.store import version_repo


class Cursor:
    lastrowid = 102
    def __init__(self): self.statements = []
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, sql, params=()): self.statements.append((sql, params))


class Connection:
    def __init__(self): self.db = Cursor()
    def cursor(self): return self.db


class VersionTests(unittest.TestCase):
    def test_replacement_requires_source_and_reason(self):
        base = {"scope": "project:x", "old_memory_id": "101",
                "client_request_id": str(uuid4()), "reason": "更新方案",
                "new_memory": {"kind": "decision", "content": "新结论",
                               "source_type": "doc", "source_excerpt": "原话"}}
        with self.assertRaises(ValidationError):
            MemoryReconcileInput.model_validate(base)
        base["new_memory"]["source_ref"] = "docs/decision.md"
        self.assertEqual(MemoryReconcileInput.model_validate(base).old_memory_id, "101")

    def test_replacement_updates_old_and_inserts_revision_in_one_transaction(self):
        connection = Connection()
        @contextmanager
        def transaction(): yield connection
        old = {"id": 101, "status": "active", "scope": "project:x"}
        new = {"id": 102, "status": "active", "scope": "project:x"}
        def row(_cursor, _scope, memory_id, **_):
            return old if str(memory_id) == "101" else new
        request = {"scope": "project:x", "old_memory_id": "101",
                   "new_memory": {"kind": "decision", "content": "新结论",
                                  "source_type": "doc", "source_ref": "docs/decision.md",
                                  "source_excerpt": "原话"},
                   "reason": "决策已更新", "client_request_id": str(uuid4())}
        with patch.object(version_repo, "_transaction", transaction), \
             patch.object(version_repo, "_claim_request", return_value=None), \
             patch.object(version_repo, "_get", side_effect=row), \
             patch.object(version_repo, "_render", side_effect=lambda _c, r, _s: r), \
             patch.object(version_repo, "_remember_response"):
            result = version_repo.reconcile(request)
        self.assertEqual(result["new_memory"]["id"], 102)
        sql = [statement for statement, _ in connection.db.statements]
        self.assertTrue(any("SET status = 'superseded'" in statement for statement in sql))
        self.assertTrue(any("INSERT INTO memory_revisions" in statement for statement in sql))

    def test_forget_detects_cached_memory_body(self):
        self.assertTrue(version_repo._contains_memory(
            {"memories": [{"id": "101", "scope": "project:x", "source_ref": "doc"}]},
            "project:x", "101"))
        self.assertFalse(version_repo._contains_memory(
            {"memory": {"id": "101", "scope": "project:other", "source_ref": "doc"}},
            "project:x", "101"))


if __name__ == "__main__": unittest.main()
