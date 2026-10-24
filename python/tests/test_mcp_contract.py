"""MCP tool registration and business-function sharing without a live database."""

import unittest
from unittest.mock import patch

from mcp.types import CallToolResult
from yanji.eval.mcp_acceptance import _result
from yanji.server.mcp_server import mcp, memory_search, memory_write


class MCPContractTests(unittest.TestCase):
    def test_acceptance_reads_actual_sdk_result_fields(self):
        result = CallToolResult(content=[], structured_content={"memory": {"id": "1"}})
        self.assertEqual(_result(result), {"memory": {"id": "1"}})
        with self.assertRaises(RuntimeError):
            _result(CallToolResult(content=[], is_error=True))

    def test_tools_are_registered_for_an_agent_host(self):
        names = {tool.name for tool in mcp._tool_manager.list_tools()}
        self.assertTrue({
            "memory_search", "memory_write", "conversation_capture",
            "memory_reconcile", "memory_handoff", "memory_forget",
        } <= names)

    def test_tools_share_http_business_functions(self):
        with patch("yanji.server.mcp_server.retrieval.search_memories", return_value={"trace_id": "t"}) as search:
            self.assertEqual(memory_search("project:x", "问题", mode="keyword"), {"trace_id": "t"})
            self.assertEqual(search.call_args.args[0].mode, "keyword")
        with patch("yanji.server.mcp_server.memory_repo.write_memory", return_value={"memory": {"id": "1"}}) as write:
            result = memory_write("project:x", "fact", "内容", "doc", "原文", source_ref="docs/example.md")
            self.assertEqual(result["memory"]["id"], "1")
            self.assertEqual(write.call_args.args[0].source_type, "doc")


if __name__ == "__main__":
    unittest.main()
