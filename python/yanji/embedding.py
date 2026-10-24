"""Reproducible local 1024-dimensional retrieval baseline.

This signed character n-gram projection is lexical rather than a neural semantic
model. It needs no API key and is useful for proving seekdb's vector path. Do not
report it as semantic embedding quality in competition results.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re

DIMENSION = 1024
MODEL_ID = "char-ngram-hash-v1"


def enabled() -> bool:
    return os.getenv("YANJI_EMBEDDING_BACKEND", "off").lower() == "hash"


def vector_for(text: str) -> list[float]:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    groups = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", normalized)
    features: list[str] = []
    for group in groups:
        if re.fullmatch(r"[\u4e00-\u9fff]+", group):
            features.extend(group[index:index + 2] for index in range(max(1, len(group) - 1)))
        else:
            features.append(group)
            if len(group) > 5:
                features.extend(group[index:index + 3] for index in range(len(group) - 2))
    vector = [0.0] * DIMENSION
    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        position = int.from_bytes(digest[:4], "big") % DIMENSION
        vector[position] += 1 if digest[4] % 2 else -1
    length = math.sqrt(sum(value * value for value in vector))
    return [round(value / length, 8) if length else 0.0 for value in vector]


def vector_json(text: str) -> str:
    return json.dumps(vector_for(text), separators=(",", ":"))
