"""Verify MCP write/search and HTTP read share a real seekdb scope.

Run after /readyz is ok: python -m yanji.eval.mcp_acceptance
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx
from mcp.client import Client


def _result(value: Any) -> dict[str, Any]:
    if value.is_error:
        raise RuntimeError(f"MCP tool returned an error: {value.content}")
    if value.structured_content is not None:
        return value.structured_content
    if value.content and value.content[0].type == "text":
        return json.loads(value.content[0].text)
    raise RuntimeError("MCP tool did not return a JSON object")


async def run(base_url: str) -> dict[str, str]:
    scope = f"mcp-acceptance:{uuid4()}"
    with httpx.Client(base_url=base_url, timeout=30.0) as http:
        http.get("/readyz").raise_for_status()
        async with Client(base_url.rstrip("/") + "/mcp") as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {"memory_write", "memory_search"} <= names
            written = _result(await client.call_tool("memory_write", {
                "scope": scope, "kind": "decision",
                "content": "MCP验收记忆应被HTTP读回。", "summary": "MCP与HTTP同库",
                "source_type": "manual", "source_ref": "acceptance:mcp",
                "source_excerpt": "MCP验收", "client_request_id": str(uuid4()),
            }))
            memory_id = written["memory"]["id"]
            response = http.get("/v1/memories", params={"scope": scope})
            response.raise_for_status()
            assert memory_id in [item["id"] for item in response.json()["items"]]
            found = _result(await client.call_tool("memory_search", {
                "scope": scope, "query": "MCP验收", "mode": "keyword",
            }))
            assert memory_id in [item["memory"]["id"] for item in found["items"]]
    result = {"scope": scope, "memory_id": memory_id, "status": "PASS"}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))
