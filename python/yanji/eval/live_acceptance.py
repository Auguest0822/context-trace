"""Run ordered D2-D5 and D9-D11 HTTP acceptance against a real local seekdb.

The script uses a new scope per run and never removes an existing conversation.
It forgets only the replacement memory that it created in its own scope.
Run after /readyz is ok: python -m yanji.eval.live_acceptance
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "data/fixtures/conversation-import.sample.json"


def _call(
    client: httpx.Client, method: str, path: str, *,
    json: dict | None = None, params: dict | None = None,
) -> dict:
    response = client.request(method, path, json=json, params=params)
    response.raise_for_status()
    return response.json()


def run(base_url: str, *, vector: bool = False) -> list[dict[str, str]]:
    scope = f"acceptance:{uuid4()}"
    checks: list[dict[str, str]] = []

    def passed(day: str, evidence: str) -> None:
        checks.append({"day": day, "status": "PASS", "evidence": evidence})
        print(f"{day} PASS: {evidence}")

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        assert _call(client, "GET", "/readyz")["status"] == "ok"
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["scope"] = scope
        fixture["client_request_id"] = str(uuid4())

        captured = _call(client, "POST", "/v1/conversations", json=fixture)
        conversation_id = captured["conversation"]["id"]
        messages = captured["messages"]
        assert captured["inserted_count"] == 4
        assert [item["role"] for item in messages] == ["user", "assistant", "user", "assistant"]
        retry = _call(client, "POST", "/v1/conversations", json=fixture)
        assert retry["conversation"]["id"] == conversation_id
        passed("D2", f"4 messages archived in scope {scope}; retry retained conversation {conversation_id}")

        listed = _call(client, "GET", "/v1/conversations", params={"scope": scope})
        detail = _call(client, "GET", f"/v1/conversations/{conversation_id}", params={"scope": scope})
        message_page = _call(
            client, "GET", f"/v1/conversations/{conversation_id}/messages",
            params={"scope": scope},
        )
        assert len(listed["items"]) == 1
        assert detail["conversation"]["id"] == conversation_id
        assert [item["sequence"] for item in message_page["items"]] == [1, 2, 3, 4]
        passed("D3", "list, detail and ordered message endpoints returned the archived fixture")

        before = _call(client, "GET", "/v1/memories", params={"scope": scope})
        assert before["items"] == []
        preview = _call(client, "POST", "/v1/extractions/preview", json={
            "scope": scope, "conversation_id": conversation_id,
            "message_ids": [messages[0]["id"]], "mode": "manual",
        })
        after_preview = _call(client, "GET", "/v1/memories", params={"scope": scope})
        assert after_preview["items"] == []
        candidate = preview["candidates"][0]
        committed = _call(
            client, "POST", f"/v1/extractions/{preview['preview_id']}/commit",
            json={
                "scope": scope, "client_request_id": str(uuid4()),
                "selected": [{"candidate_id": candidate["candidate_id"],
                              "kind": "decision", "content": candidate["content"],
                              "summary": "初赛保证仓库复现"}],
            },
        )
        memory = committed["memories"][0]
        assert memory["source_message_ids"] == [messages[0]["id"]]
        assert memory["source_excerpt"] in messages[0]["content"]
        passed("D4", f"preview wrote 0 memories; confirmation wrote memory {memory['id']} with evidence")

        search = _call(client, "POST", "/v1/memories/search", json={
            "scope": scope, "query": "初赛", "mode": "keyword", "top_k": 5,
        })
        assert memory["id"] in [item["memory"]["id"] for item in search["items"]]
        assert search["mode_used"] == "keyword" and search["trace_id"]
        passed("D5", "keyword search returned the confirmed memory and its source")

        if vector:
            vector_search = _call(client, "POST", "/v1/memories/search", json={
                "scope": scope, "query": "初赛", "mode": "vector", "top_k": 5,
            })
            hybrid_search = _call(client, "POST", "/v1/memories/search", json={
                "scope": scope, "query": "初赛", "mode": "hybrid", "top_k": 5,
            })
            assert vector_search["mode_used"] == "vector"
            assert hybrid_search["mode_used"] == "hybrid"
            passed("D8", "seekdb vector and hybrid SQL both returned their requested mode")

        selected = _call(client, "POST", "/v1/memories/context", json={
            "scope": scope, "memory_ids": [memory["id"]], "budget_tokens": 1200,
        })
        empty = _call(client, "POST", "/v1/memories/context", json={
            "scope": scope, "memory_ids": [], "budget_tokens": 1200,
        })
        assert selected["included_memory_ids"] == [memory["id"]]
        assert memory["source_ref"] in selected["context_text"]
        assert empty["included_memory_ids"] == [] and empty["context_text"] == ""
        long_memory = _call(client, "POST", "/v1/memories", json={
            "scope": scope, "kind": "fact", "content": "长文本预算测试。" * 200,
            "summary": "短摘要", "source_type": "manual",
            "source_ref": "acceptance:budget", "source_excerpt": "长文本预算测试。",
            "client_request_id": str(uuid4()),
        })["memory"]
        compressed = _call(client, "POST", "/v1/memories/context", json={
            "scope": scope, "memory_ids": [long_memory["id"]], "budget_tokens": 100,
        })
        assert compressed["items"][0]["selected_form"] == "summary"
        assert compressed["budget"]["used_tokens"] <= 100
        assert long_memory["source_ref"] in compressed["context_text"]
        passed("D9", "selection and empty context respected; long content used a sourced summary within 100 tokens")

        replacement = _call(client, "POST", "/v1/memories/reconcile", json={
            "scope": scope, "old_memory_id": memory["id"],
            "new_memory": {
                "kind": "decision", "content": "初赛优先仓库复现并保留来源。",
                "summary": "优先仓库复现", "source_type": "chat",
                "conversation_id": conversation_id,
                "source_message_ids": [messages[0]["id"]],
                "source_excerpt": "初赛先保证评委从仓库能复现完整流程。",
            },
            "reason": "验收新决定替代旧决定", "client_request_id": str(uuid4()),
        })
        new_id = replacement["new_memory"]["id"]
        history = _call(client, "GET", f"/v1/memories/{memory['id']}/history",
                        params={"scope": scope})
        assert [item["memory"]["id"] for item in history["items"]] == [memory["id"], new_id]
        active = _call(client, "GET", "/v1/memories", params={"scope": scope, "status": "active"})
        assert memory["id"] not in [item["id"] for item in active["items"]]
        forgotten = _call(client, "DELETE", f"/v1/memories/{new_id}", params={"scope": scope})
        assert forgotten["deleted"] is True
        missing = client.get(f"/v1/memories/{new_id}", params={"scope": scope})
        assert missing.status_code == 404
        passed("D10", "version history, active filter and generated-memory forget succeeded")

        handoff_memory = _call(client, "POST", "/v1/memories", json={
            "scope": scope, "kind": "decision", "content": "初赛仓库复现须保留来源。",
            "summary": "保留来源", "source_type": "manual",
            "source_ref": "acceptance:handoff", "source_excerpt": "初赛仓库复现",
            "client_request_id": str(uuid4()),
        })["memory"]
        traces = _call(client, "GET", "/v1/traces", params={"scope": scope})
        trace = _call(client, "GET", f"/v1/traces/{search['trace_id']}", params={"scope": scope})
        handoff = _call(client, "POST", "/v1/memories/handoff", json={
            "scope": scope, "objective": "初赛仓库复现", "budget_tokens": 1200,
        })
        assert any(item["trace_id"] == search["trace_id"] for item in traces["items"])
        assert trace["trace_id"] == search["trace_id"]
        assert handoff_memory["id"] in handoff["memory_ids"]
        passed("D11", "trace list/detail and sourced handoff returned the active memory")

    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--vector", action="store_true", help="require vector and hybrid SQL checks")
    args = parser.parse_args()
    run(args.base_url, vector=args.vector)
