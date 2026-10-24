"""Verify the HTTP boundary and its contract without requiring a running seekdb."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pymysql.err import OperationalError
from yanji.server.api import app
from yanji.store.repo import IdempotencyConflict, NotFound, StateConflict

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = json.loads(
    (ROOT / "data/fixtures/conversation-import.sample.json").read_text(encoding="utf-8")
)


class ConversationHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_capture_status_and_public_response(self) -> None:
        for created, status in ((True, 201), (False, 200)):
            with self.subTest(created=created):
                stored = {
                    "conversation": {"id": "201", "scope": SAMPLE["scope"]},
                    "messages": [{"id": "301", "role": "user"}],
                    "inserted_count": 1 if created else 0,
                    "created": created,
                }
                with patch("yanji.server.api.repo.capture_conversation", return_value=stored) as save:
                    response = self.client.post("/v1/conversations", json=SAMPLE)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("created", response.json())
                self.assertEqual(response.json()["conversation"]["id"], "201")
                self.assertEqual(save.call_args.args[0].scope, SAMPLE["scope"])
                self.assertIn("X-Request-ID", response.headers)

    def test_append_and_read_routes_forward_scope_and_pagination(self) -> None:
        appended = {"conversation": {"id": "201"}, "messages": [], "inserted_count": 0}
        payload = {"scope": SAMPLE["scope"], "messages": [SAMPLE["messages"][0]]}
        with patch("yanji.server.api.repo.append_messages", return_value=appended) as save:
            response = self.client.post("/v1/conversations/201/messages", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(save.call_args.args[0], "201")
        self.assertEqual(save.call_args.args[1].scope, SAMPLE["scope"])

        page = {"items": [{"id": "201"}], "next_cursor": "opaque"}
        with patch("yanji.server.api.repo.list_conversations", return_value=page) as listing:
            response = self.client.get(
                "/v1/conversations", params={
                    "scope": SAMPLE["scope"], "platform": "deepseek", "limit": 1,
                    "cursor": "previous", "q": "部署",
                },
            )
        self.assertEqual(response.json(), page)
        self.assertEqual(listing.call_args.args[0], SAMPLE["scope"])
        self.assertEqual(listing.call_args.kwargs["limit"], 1)
        self.assertEqual(listing.call_args.kwargs["cursor"], "previous")

        with patch("yanji.server.api.repo.get_conversation", return_value={"id": "201"}) as get:
            response = self.client.get("/v1/conversations/201", params={"scope": SAMPLE["scope"]})
        self.assertEqual(response.json(), {"conversation": {"id": "201"}})
        self.assertEqual(get.call_args.args, (SAMPLE["scope"], "201"))

        messages = {"items": [{"id": "301", "sequence": 0}], "next_cursor": None}
        with patch("yanji.server.api.repo.list_messages", return_value=messages) as listing:
            response = self.client.get(
                "/v1/conversations/201/messages",
                params={"scope": SAMPLE["scope"], "limit": 10, "cursor": "next"},
            )
        self.assertEqual(response.json(), messages)
        self.assertEqual(listing.call_args.args, (SAMPLE["scope"], "201"))
        self.assertEqual(listing.call_args.kwargs, {"limit": 10, "cursor": "next"})

    def test_invalid_requests_do_not_reach_storage(self) -> None:
        cases = (
            ("post", "/v1/conversations", {**SAMPLE, "unexpected": True}, None),
            ("get", "/v1/conversations", None, None),
            ("get", "/v1/conversations", None, {"scope": "   "}),
            ("get", "/v1/conversations/nope", None, {"scope": SAMPLE["scope"]}),
            ("get", "/v1/conversations", None, {"scope": SAMPLE["scope"], "limit": 101}),
            ("get", "/v1/conversations", None, {"scope": SAMPLE["scope"], "typo": "1"}),
        )
        with patch("yanji.server.api.repo.capture_conversation") as save:
            for method, path, body, params in cases:
                with self.subTest(path=path, body=body, params=params):
                    response = self.client.request(method, path, json=body, params=params)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
            save.assert_not_called()

    def test_errors_keep_contract_codes_and_hide_database_details(self) -> None:
        for error, status, code in (
            (NotFound("conversation not found in this scope"), 404, "NOT_FOUND"),
            (StateConflict("archived message differs"), 409, "STATE_CONFLICT"),
            (IdempotencyConflict("request key reused"), 409, "IDEMPOTENCY_CONFLICT"),
            (OperationalError(2003, "secret database host"), 503, "STORE_UNAVAILABLE"),
        ):
            with self.subTest(code=code):
                with patch("yanji.server.api.repo.get_conversation", side_effect=error):
                    response = self.client.get(
                        "/v1/conversations/201", params={"scope": SAMPLE["scope"]}
                    )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertEqual(
                    response.json()["error"]["request_id"], response.headers["X-Request-ID"]
                )
                self.assertNotIn("secret database host", response.text)

    def test_health_and_database_readiness(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        with patch("yanji.server.api.check_connection", return_value=True):
            self.assertEqual(self.client.get("/readyz").status_code, 200)
        with patch("yanji.server.api.check_connection", return_value=False):
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "STORE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
