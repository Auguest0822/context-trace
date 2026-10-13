"""Runtime settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SeekDBSettings:
    host: str = "127.0.0.1"
    port: int = 2881
    user: str = "root"
    password: str = ""
    database: str = "context_trace"
    embedding_dim: int = 1024

    @classmethod
    def from_env(cls) -> SeekDBSettings:
        """Read connection settings; do not log or display the password."""
        port = int(os.getenv("SEEKDB_PORT", "2881"))
        dim = int(os.getenv("SEEKDB_EMBEDDING_DIM", "1024"))
        if not 1 <= port <= 65535:
            raise ValueError("SEEKDB_PORT must be between 1 and 65535")
        if dim != 1024:
            raise ValueError("The current schema requires SEEKDB_EMBEDDING_DIM=1024")
        database = os.getenv("SEEKDB_DATABASE", "context_trace")
        if not database or not all(ch.isalnum() or ch == "_" for ch in database):
            raise ValueError("SEEKDB_DATABASE must contain only letters, digits or underscores")
        return cls(
            host=os.getenv("SEEKDB_HOST", "127.0.0.1"),
            port=port,
            user=os.getenv("SEEKDB_USER", "root"),
            password=os.getenv("SEEKDB_PASSWORD", ""),
            database=database,
            embedding_dim=dim,
        )
