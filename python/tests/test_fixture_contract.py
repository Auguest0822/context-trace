"""Keep synthetic conversations and expected memories tied to real source text."""

import json
import unittest
from collections import Counter
from pathlib import Path
from uuid import UUID

from yanji.models import ConversationInput


ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_FILES = (
    "data/fixtures/conversation-import.sample.json",
    "data/fixtures/conversation-import.kimi.sample.json",
)
MEMORIES_FILE = "docs/samples/memories.sample.json"
SEARCH_CASES_FILE = "docs/samples/search-cases.sample.json"


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class FixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conversations = {path: load_json(path) for path in CONVERSATION_FILES}
        cls.memories = load_json(MEMORIES_FILE)
        cls.search_cases = load_json(SEARCH_CASES_FILE)

    def test_conversation_inputs_cover_d1(self):
        for path, data in self.conversations.items():
            with self.subTest(path=path):
                ConversationInput.model_validate(data)
                self.assertEqual(data["capture_method"], "manual_import")
                self.assertIsNone(data["source_url"])
        total_messages = sum(len(item["messages"]) for item in self.conversations.values())
        self.assertGreaterEqual(total_messages, 10)
        self.assertLessEqual(total_messages, 20)
        self.assertGreaterEqual(len({item["platform"] for item in self.conversations.values()}), 2)

    def test_memory_expectations_have_verifiable_sources(self):
        self.assertEqual(len(self.memories), 15)
        self.assertEqual(
            Counter(memory["kind"] for memory in self.memories),
            {kind: 3 for kind in ("decision", "constraint", "fact", "preference", "skill")},
        )
        keys = [memory["fixture_key"] for memory in self.memories]
        self.assertEqual(len(keys), len(set(keys)))
        generated_fields = {"id", "status", "source_platform", "conversation_id", "source_message_ids"}
        for memory in self.memories:
            with self.subTest(fixture_key=memory["fixture_key"]):
                self.assertFalse(generated_fields.intersection(memory))
                self.assertTrue(memory["content"].strip())
                self.assertTrue(memory["summary"].strip())
                self.assertTrue(0 <= memory["importance"] <= 1)
                self.assertTrue(memory["source_excerpt"].strip())
                if memory["source_type"] == "chat":
                    self.assertNotIn("source_ref", memory)
                    fixture = self.conversations[memory["conversation_fixture"]]
                    self.assertEqual(memory["scope"], fixture["scope"])
                    selected = [
                        msg for msg in fixture["messages"]
                        if msg["sequence"] in memory["source_message_sequences"]
                    ]
                    self.assertEqual(len(selected), len(memory["source_message_sequences"]))
                    self.assertTrue(any(msg["role"] == "user" for msg in selected))
                    self.assertTrue(
                        any(memory["source_excerpt"] in msg["content"] for msg in selected)
                    )
                else:
                    self.assertEqual(memory["source_type"], "doc")
                    self.assertNotIn("conversation_fixture", memory)
                    self.assertNotIn("source_message_sequences", memory)
                    source_path = memory["source_ref"].split("#", 1)[0]
                    self.assertTrue(source_path.startswith("docs/"))
                    self.assertTrue(
                        memory["source_excerpt"] in (ROOT / source_path).read_text(encoding="utf-8"),
                        f"{memory['fixture_key']}: excerpt not found in {source_path}",
                    )

    def test_direct_document_write_input_and_search_cases(self):
        direct = load_json("data/fixtures/memory-write.doc.sample.json")
        expected = next(
            memory for memory in self.memories
            if memory["fixture_key"] == "repo-reproducibility"
        )
        for field in ("scope", "kind", "content", "summary", "importance", "source_type",
                      "source_ref", "source_excerpt"):
            self.assertEqual(direct[field], expected[field])
        self.assertEqual(direct["source_type"], "doc")
        self.assertEqual(len(direct.keys() - {
            "scope", "kind", "content", "summary", "importance", "source_type",
            "source_ref", "source_excerpt", "valid_from", "valid_to", "client_request_id",
        }), 0)
        UUID(direct["client_request_id"])
        memory_keys = {memory["fixture_key"] for memory in self.memories}
        case_ids = [case["case_id"] for case in self.search_cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for case in self.search_cases:
            with self.subTest(case_id=case["case_id"]):
                request = case["request"]
                self.assertIn(case["phase"], {"D5", "D8"})
                self.assertIn(request["mode"], {"keyword", "vector", "hybrid"})
                self.assertTrue(1 <= request["top_k"] <= 20)
                self.assertTrue(100 <= request["budget_tokens"] <= 8192)
                self.assertTrue(request["query"].strip())
                expected_include = set(case.get("expected_include", []))
                expected_exclude = set(case.get("expected_exclude", []))
                self.assertFalse(expected_include & expected_exclude)
                self.assertTrue((expected_include | expected_exclude) <= memory_keys)
                if case.get("expected_empty"):
                    self.assertFalse(expected_include)


if __name__ == "__main__":
    unittest.main()
