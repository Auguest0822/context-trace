"""Import one JSON conversation through the same repository path as the future API."""

from __future__ import annotations

import argparse
import getpass
import json
from dataclasses import replace
from pathlib import Path

from yanji.config import SeekDBSettings
from yanji.store.repo import capture_conversation


def main() -> None:
    parser = argparse.ArgumentParser(description="Import one confirmed conversation JSON file")
    parser.add_argument("file", type=Path, help="JSON file matching POST /v1/conversations")
    parser.add_argument("--prompt-password", action="store_true")
    args = parser.parse_args()
    settings = SeekDBSettings.from_env()
    if args.prompt_password:
        settings = replace(settings, password=getpass.getpass("seekdb password: "))
    data = json.loads(args.file.read_text(encoding="utf-8"))
    result = capture_conversation(data, settings)
    print(
        f"conversation_id={result['conversation']['id']} "
        f"message_count={result['conversation']['message_count']} "
        f"inserted_count={result['inserted_count']}"
    )


if __name__ == "__main__":
    main()
