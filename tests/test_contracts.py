"""Tests for JSON schema validation (qa.validate_schema)"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_podcast_pipeline.qa import validate_schema


SCRIPT_SCHEMA_PATH = Path("schemas/script.schema.json")
SOURCES_SCHEMA_PATH = Path("schemas/sources.schema.json")
MANIFEST_SCHEMA_PATH = Path("schemas/manifest.schema.json")


def _write_json(data: dict, suffix: str = ".json") -> Path:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


def _valid_script() -> dict:
    return {
        "episode_name": "The Signal – March 1, 2026",
        "generated_at": "2026-03-01T12:00:00+00:00",
        "intro": "Welcome to The Signal.",
        "stories": [
            {
                "index": 1,
                "title": "AI Story",
                "source_domain": "venturebeat.com",
                "source_url": "https://venturebeat.com/article",
                "published_at": "2026-02-28T10:00:00+00:00",
                "narrative": "This is a narrative.",
            }
        ],
        "cn_relevance": None,
        "ending_segment": "Food for Thought",
        "food_for_thought": "Something to think about.",
        "word_count": 100,
        "script_markdown": "Script text here.",
        "rewrite_attempts": 0,
        "explicit_fail_state": False,
    }


@unittest.skipUnless(SCRIPT_SCHEMA_PATH.exists(), "schemas dir not found — run tests from project root")
class TestScriptSchema(unittest.TestCase):
    def test_valid_script_passes(self):
        path = _write_json(_valid_script())
        ok, errors = validate_schema(path, SCRIPT_SCHEMA_PATH)
        self.assertTrue(ok, errors)

    def test_missing_ending_segment_fails(self):
        data = _valid_script()
        del data["ending_segment"]
        path = _write_json(data)
        ok, errors = validate_schema(path, SCRIPT_SCHEMA_PATH)
        self.assertFalse(ok)

    def test_invalid_rewrite_attempts_fails(self):
        data = _valid_script()
        data["rewrite_attempts"] = 99  # above maximum of 2
        path = _write_json(data)
        ok, errors = validate_schema(path, SCRIPT_SCHEMA_PATH)
        self.assertFalse(ok)

    def test_empty_stories_fails(self):
        data = _valid_script()
        data["stories"] = []
        path = _write_json(data)
        ok, errors = validate_schema(path, SCRIPT_SCHEMA_PATH)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
