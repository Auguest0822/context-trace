"""Fill missing vectors for confirmed memories in one scope.

Run with YANJI_EMBEDDING_BACKEND=hash. Existing data is never overwritten.
"""

from __future__ import annotations

import argparse

from yanji import embedding
from yanji.store.repo import _transaction


def backfill(scope: str, batch_size: int = 50) -> int:
    if not embedding.enabled():
        raise RuntimeError("set YANJI_EMBEDDING_BACKEND=hash before backfill")
    if not scope.strip() or not 1 <= batch_size <= 500:
        raise ValueError("invalid scope or batch_size")
    updated = 0
    last_id = 0
    while True:
        with _transaction() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, content FROM memories WHERE scope = %s AND embedding IS NULL "
                "AND id > %s ORDER BY id ASC LIMIT %s FOR UPDATE",
                (scope, last_id, batch_size),
            )
            rows = cursor.fetchall()
            for row in rows:
                cursor.execute(
                    "UPDATE memories SET embedding = %s, embedding_model = %s, "
                    "embedding_dim = %s WHERE id = %s AND scope = %s AND embedding IS NULL",
                    (embedding.vector_json(row["content"]), embedding.MODEL_ID,
                     embedding.DIMENSION, row["id"], scope),
                )
            updated += len(rows)
            if rows:
                last_id = rows[-1]["id"]
        if len(rows) < batch_size:
            break
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    print(f"backfilled {backfill(args.scope, args.batch_size)} memories")
