"""Idempotently load synthetic conversations and confirmed benchmark memories.

This is demonstration data, never a substitute for the D4 user confirmation flow.
Run from the repository root after schema bootstrap: python -m yanji.store.seed_demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from yanji.store import memory_repo, repo

ROOT = Path(__file__).resolve().parents[3]
CONVERSATIONS = (
    ROOT / "data/fixtures/conversation-import.sample.json",
    ROOT / "data/fixtures/conversation-import.kimi.sample.json",
)
MEMORIES = ROOT / "docs/samples/memories.sample.json"


def seed(scope: str | None = None) -> dict[str, int]:
    archived = {}
    for path in CONVERSATIONS:
        conversation_payload = json.loads(path.read_text(encoding="utf-8"))
        if scope is not None:
            conversation_payload["scope"] = scope
        result = repo.capture_conversation(conversation_payload)
        archived[path.resolve()] = result
    created = 0
    for item in json.loads(MEMORIES.read_text(encoding="utf-8")):
        payload = {key: value for key, value in item.items()
                   if key not in {"fixture_key", "conversation_fixture", "source_message_sequences"}}
        if scope is not None:
            payload["scope"] = scope
        payload["client_request_id"] = str(uuid5(NAMESPACE_URL, f"context-trace-demo:{item['fixture_key']}"))
        if item["source_type"] == "chat":
            path = (ROOT / item["conversation_fixture"]).resolve()
            conversation = archived[path]
            by_sequence = {message["sequence"]: message["id"]
                           for message in conversation["messages"]}
            payload["conversation_id"] = conversation["conversation"]["id"]
            payload["source_message_ids"] = [
                by_sequence[sequence] for sequence in item["source_message_sequences"]
            ]
        result = memory_repo.write_memory(payload)
        created += int(result["created"])
    return {"conversations": len(archived), "memories_created": created}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", help="override scope for an isolated benchmark dataset")
    args = parser.parse_args()
    print(seed(args.scope))
