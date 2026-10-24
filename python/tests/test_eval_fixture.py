import json
import unittest

from yanji.eval.run_benchmark import MEMORIES, QUESTIONS


class EvalFixtureTests(unittest.TestCase):
    def test_thirty_questions_have_seeded_answers(self):
        questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
        keys = {item["fixture_key"] for item in json.loads(MEMORIES.read_text(encoding="utf-8"))}
        self.assertEqual(len(questions), 30)
        self.assertEqual(len({item["id"] for item in questions}), 30)
        self.assertTrue(all(item["query"].strip() and item["expected"] in keys
                            for item in questions))


if __name__ == "__main__": unittest.main()
