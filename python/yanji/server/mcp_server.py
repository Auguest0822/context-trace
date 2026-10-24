"""Agent tools over the same validated storage functions as HTTP.

Tools receive only arguments supplied by the host; they never read hidden history.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from yanji.models import (
    ConversationInput,
    MemoryHandoffInput,
    MemoryReconcileInput,
    MemorySearchInput,
    MemoryWriteInput,
)
from yanji.store import memory_repo, repo, retrieval, version_repo

mcp = MCPServer("ContextTrace", description="Confirmed memories with verifiable sources")


@mcp.tool(description="Search confirmed memories in one scope, with source references. Use keyword mode until an embedding provider is configured.")
def memory_search(
    scope: str, query: str, mode: str = "hybrid", top_k: int = 5,
    budget_tokens: int = 1200, filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = MemorySearchInput.model_validate({
        "scope": scope, "query": query, "mode": mode, "top_k": top_k,
        "budget_tokens": budget_tokens, "filters": filters or {},
    })
    return retrieval.search_memories(request)


@mcp.tool(description="Write one user-confirmed memory with verifiable source. Chat sources must cite archived message IDs in the same scope.")
def memory_write(
    scope: str, kind: str, content: str, source_type: str, source_excerpt: str,
    source_ref: str | None = None, summary: str | None = None,
    importance: float = 0.5, conversation_id: str | None = None,
    source_message_ids: list[str] | None = None, client_request_id: str | None = None,
) -> dict[str, Any]:
    request = MemoryWriteInput.model_validate({
        "scope": scope, "kind": kind, "content": content,
        "source_type": source_type, "source_excerpt": source_excerpt,
        "source_ref": source_ref, "summary": summary, "importance": importance,
        "conversation_id": conversation_id, "source_message_ids": source_message_ids,
        "client_request_id": client_request_id,
    })
    return {"memory": memory_repo.write_memory(request)["memory"]}


@mcp.tool(description="Archive only messages supplied by the Agent host and confirmed by the user; this tool cannot read hidden conversation history.")
def conversation_capture(conversation: dict[str, Any]) -> dict[str, Any]:
    request = ConversationInput.model_validate(conversation)
    result = repo.capture_conversation(request)
    result.pop("created", None)
    return result


@mcp.tool(description="Replace one explicitly named active memory with a new sourced conclusion and a reason. This is atomic and preserves history.")
def memory_reconcile(request: dict[str, Any]) -> dict[str, Any]:
    return version_repo.reconcile(MemoryReconcileInput.model_validate(request))


@mcp.tool(description="Prepare a sourced handoff context from confirmed memories for a stated objective.")
def memory_handoff(
    scope: str, objective: str, budget_tokens: int = 1200,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = MemoryHandoffInput.model_validate({
        "scope": scope, "objective": objective, "budget_tokens": budget_tokens,
        "filters": filters or {},
    })
    return retrieval.handoff(request)


@mcp.tool(description="Permanently forget a specific memory after the user explicitly asks; remove its body, vector, evidence links and trace references.")
def memory_forget(scope: str, memory_id: str) -> dict[str, Any]:
    return version_repo.forget(scope, memory_id)
