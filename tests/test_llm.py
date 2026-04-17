"""Tests for ai_podcast_pipeline.llm"""
from __future__ import annotations

import json
import unittest

from ai_podcast_pipeline.llm import OpenAIError, parse_json_response


class TestParseJsonResponse(unittest.TestCase):
    def test_plain_json(self):
        content = '{"key": "value"}'
        result = parse_json_response(content)
        self.assertEqual(result, {"key": "value"})

    def test_json_with_whitespace(self):
        content = '  \n{"key": "value"}\n  '
        result = parse_json_response(content)
        self.assertEqual(result, {"key": "value"})

    def test_fenced_json_block(self):
        content = '```json\n{"key": "value"}\n```'
        result = parse_json_response(content)
        self.assertEqual(result, {"key": "value"})

    def test_fenced_block_no_language_tag(self):
        content = '```\n{"key": "value"}\n```'
        result = parse_json_response(content)
        self.assertEqual(result, {"key": "value"})

    def test_invalid_json_raises(self):
        with self.assertRaises(OpenAIError):
            parse_json_response("not json at all")

    def test_fenced_block_with_trailing_text(self):
        # The fence stripping should handle even extra whitespace.
        content = '```json\n{"a": 1}\n```\n'
        result = parse_json_response(content)
        self.assertEqual(result, {"a": 1})

    def test_nested_json(self):
        payload = {"stories": ["a", "b"], "cn_relevance": None, "food_for_thought": "text"}
        content = json.dumps(payload)
        result = parse_json_response(content)
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
