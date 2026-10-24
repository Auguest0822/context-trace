"""Evaluate 30 fixed questions against seeded synthetic memories in real seekdb."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from yanji import embedding
from yanji.store.client import connect
from yanji.store.retrieval import search_memories

ROOT = Path(__file__).resolve().parents[3]
QUESTIONS = ROOT / "data/fixtures/search-eval.json"
MEMORIES = ROOT / "docs/samples/memories.sample.json"


def _mapping(scope: str) -> dict[str, str]:
    fixtures = json.loads(MEMORIES.read_text(encoding="utf-8"))
    request_ids = {item["fixture_key"]: str(uuid5(
        NAMESPACE_URL, f"context-trace-demo:{item['fixture_key']}"
    )) for item in fixtures}
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, client_request_id FROM memories WHERE scope = %s "
            "AND client_request_id IS NOT NULL", (scope,),
        )
        rows = cursor.fetchall()
    by_request = {row["client_request_id"]: str(row["id"]) for row in rows}
    missing = sorted(key for key, request_id in request_ids.items() if request_id not in by_request)
    if missing:
        raise RuntimeError("seed demo memories before benchmarking; missing: " + ", ".join(missing))
    return {key: by_request[request_id] for key, request_id in request_ids.items()}


def evaluate(scope: str, modes: list[str], budgets: list[int]) -> dict:
    mapping = _mapping(scope)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if len(questions) != 30 or any(question["expected"] not in mapping for question in questions):
        raise RuntimeError("fixed evaluation questions do not match seeded memories")
    runs: list[dict[str, Any]] = []
    for mode in modes:
        if mode != "keyword" and not embedding.enabled():
            runs.append({"mode": mode, "status": "embedding_unavailable"})
            continue
        for budget in budgets:
            records = []
            for question in questions:
                result = search_memories({
                    "scope": scope, "query": question["query"], "mode": mode,
                    "top_k": 5, "budget_tokens": budget,
                })
                ids = [item["memory"]["id"] for item in result["items"]]
                expected_id = mapping[question["expected"]]
                records.append({
                    "question_id": question["id"], "expected_memory_id": expected_id,
                    "returned_ids": ids, "hit_at_1": bool(ids and ids[0] == expected_id),
                    "hit_at_5": expected_id in ids,
                    "elapsed_ms": result["elapsed_ms"],
                    "used_tokens": result["budget"]["used_tokens"],
                    "trace_id": result["trace_id"],
                })
            elapsed = sorted(record["elapsed_ms"] for record in records)
            runs.append({
                "mode": mode, "budget_tokens": budget, "status": "measured",
                "questions": len(records),
                "hit_at_1": sum(record["hit_at_1"] for record in records) / len(records),
                "hit_at_5": sum(record["hit_at_5"] for record in records) / len(records),
                "latency_ms_median": statistics.median(elapsed),
                "latency_ms_p95": elapsed[max(0, math.ceil(len(elapsed) * .95) - 1)],
                "mean_used_tokens": round(statistics.mean(
                    record["used_tokens"] for record in records), 2),
                "records": records,
            })
    return {
        "generated_at": datetime.now(UTC).isoformat(), "scope": scope,
        "dataset": str(QUESTIONS.relative_to(ROOT)).replace("\\", "/"),
        "embedding_backend": embedding.MODEL_ID if embedding.enabled() else "off",
        "expected_memories": len(mapping), "question_count": len(questions),
        "latency_scope": "retrieval and context assembly before trace persistence",
        "tokenizer": "utf8-bytes/3 (estimate)", "top_k": 5,
        "runs": runs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", default="benchmark:context-trace-v1")
    parser.add_argument("--output", default=str(ROOT / "docs/benchmark-results.json"))
    parser.add_argument("--modes", nargs="+", choices=["keyword", "vector", "hybrid"],
                        default=["keyword", "vector", "hybrid"])
    parser.add_argument("--budgets", nargs="+", type=int, default=[1200, 8192])
    args = parser.parse_args()
    report = evaluate(args.scope, args.modes, args.budgets)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    for run in report["runs"]:
        print({key: value for key, value in run.items() if key != "records"})
