"""seekdb connection and first-time schema bootstrap."""

from __future__ import annotations

import argparse
import getpass
from dataclasses import replace
from pathlib import Path

import pymysql
from pymysql.connections import Connection

from yanji.config import SeekDBSettings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
EXPECTED_TABLES = frozenset(
    {
        "conversations",
        "messages",
        "extraction_previews",
        "memories",
        "memory_message_links",
        "retrieval_traces",
        "retrieval_trace_items",
        "memory_revisions",
        "idempotency_requests",
    }
)


def connect(settings: SeekDBSettings | None = None) -> Connection:
    """Connect over seekdb's MySQL protocol, with UTC session timestamps."""
    settings = settings or SeekDBSettings.from_env()
    connection = pymysql.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        database=settings.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
    except Exception:
        connection.close()
        raise
    return connection


def check_connection(settings: SeekDBSettings | None = None) -> bool:
    """Return True after a round trip to the configured database."""
    with connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 AS ok")
        return cursor.fetchone()["ok"] == 1


def _existing_tables(connection: Connection) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        return {next(iter(row.values())) for row in cursor.fetchall()}


def _assert_no_draft_schema(connection: Connection) -> None:
    if "memories" not in _existing_tables(connection):
        return
    with connection.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM memories")
        columns = {row["Field"] for row in cursor.fetchall()}
    required = {"source_excerpt", "source_platform", "embedding_model", "client_request_id"}
    if not required <= columns:
        raise RuntimeError(
            "An older memories table exists. Back it up and migrate it explicitly; "
            "schema bootstrap does not overwrite existing data."
        )


def initialize_schema(settings: SeekDBSettings | None = None) -> list[str]:
    """Create missing tables on a fresh database; keep any existing data."""
    sql_lines = [
        line for line in SCHEMA_PATH.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ]
    statements = [part.strip() for part in "\n".join(sql_lines).split(";") if part.strip()]
    with connect(settings) as connection:
        _assert_no_draft_schema(connection)
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
        connection.commit()
        missing = EXPECTED_TABLES - _existing_tables(connection)
        if missing:
            raise RuntimeError(f"Schema bootstrap incomplete: {', '.join(sorted(missing))}")
    return sorted(EXPECTED_TABLES)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check or initialize the seekdb database")
    parser.add_argument("--check", action="store_true", help="test the database connection")
    parser.add_argument("--init-schema", action="store_true", help="create missing tables")
    parser.add_argument("--prompt-password", action="store_true", help="read password without echo")
    args = parser.parse_args()
    if not args.check and not args.init_schema:
        parser.error("choose --check and/or --init-schema")
    settings = SeekDBSettings.from_env()
    if args.prompt_password:
        settings = replace(settings, password=getpass.getpass("seekdb password: "))
    if args.check:
        check_connection(settings)
        print("seekdb connection: OK")
    if args.init_schema:
        tables = initialize_schema(settings)
        print(f"seekdb schema: OK ({len(tables)} tables)")


if __name__ == "__main__":
    main()
