"""New HTTP route boundaries and their error/status contract."""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from yanji.server.api import app


class MemoryHttpTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.scope = "project:context-trace"

    def test_list_search_and_context_are_distinct_routes(self):
        with patch("yanji.server.api.retrieval.list_memories", return_value={"items": [], "next_cursor": None}):
            response = self.client.get("/v1/memories", params={"scope": self.scope, "status": "active"})
        self.assertEqual(response.status_code, 200)
        with patch("yanji.server.api.retrieval.search_memories", return_value={"trace_id": "t", "items": []}) as search:
            response = self.client.post("/v1/memories/search", json={
                "scope": self.scope, "query": "初赛", "mode": "keyword"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.args[0].mode, "keyword")
        with patch("yanji.server.api.retrieval.assemble_context", return_value={"included_memory_ids": []}) as context:
            response = self.client.post("/v1/memories/context", json={
                "scope": self.scope, "memory_ids": [], "budget_tokens": 100})
        self.assertEqual(response.json()["included_memory_ids"], [])
        self.assertEqual(context.call_args.args[0].memory_ids, [])

    def test_write_rejects_forged_chat_source_before_storage(self):
        payload = {"scope": self.scope, "kind": "decision", "content": "结论",
                   "source_type": "chat", "source_ref": "invented", "source_excerpt": "原文",
                   "conversation_id": "1", "source_message_ids": ["2"]}
        with patch("yanji.server.api.memory_repo.write_memory") as write:
            response = self.client.post("/v1/memories", json=payload)
        self.assertEqual(response.status_code, 400)
        write.assert_not_called()

    def test_reconcile_requires_source_and_trace_scope(self):
        response = self.client.post("/v1/memories/reconcile", json={
            "scope": self.scope, "old_memory_id": "1", "reason": "更新",
            "new_memory": {"kind": "fact", "content": "结论", "source_type": "doc",
                           "source_excerpt": "原文"},
            "client_request_id": str(uuid4()),
        })
        self.assertEqual(response.status_code, 400)
        with patch("yanji.server.api.trace_repo.get_trace", return_value={"trace_id": str(uuid4())}) as get:
            response = self.client.get(f"/v1/traces/{uuid4()}", params={"scope": self.scope})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_args.args[0], self.scope)


if __name__ == "__main__": unittest.main()
