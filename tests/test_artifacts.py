"""Tests for ai_podcast_pipeline.artifacts"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_podcast_pipeline.artifacts import (
    build_artifact_paths,
    build_episode_base_name,
    format_episode_date,
    resolve_episode_name,
    resolve_episode_number,
)
from ai_podcast_pipeline.constants import TIMEZONE


class TestFormatEpisodeDate(unittest.TestCase):
    def test_no_leading_zero(self):
        dt = datetime(2026, 3, 1, tzinfo=ZoneInfo(TIMEZONE))
        self.assertEqual(format_episode_date(dt), "March 1, 2026")

    def test_double_digit_day(self):
        dt = datetime(2026, 11, 15, tzinfo=ZoneInfo(TIMEZONE))
        self.assertEqual(format_episode_date(dt), "November 15, 2026")


class TestBuildEpisodeBaseName(unittest.TestCase):
    def test_format(self):
        dt = datetime(2026, 3, 1, 12, 0, 0, tzinfo=ZoneInfo(TIMEZONE))
        name = build_episode_base_name(now=dt)
        self.assertIn("March 1, 2026", name)
        self.assertIn("The Signal", name)


class TestResolveEpisodeNumber(unittest.TestCase):
    def test_returns_1_for_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(resolve_episode_number(Path(d)), 1)

    def test_increments_from_existing(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d) / "The Signal \u2013 March 1, 2026 - Manifest.json"
            manifest.write_text(json.dumps({"episode_number": 5}), encoding="utf-8")
            self.assertEqual(resolve_episode_number(Path(d)), 6)

    def test_handles_missing_episode_number_field(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d) / "The Signal \u2013 March 1, 2026 - Manifest.json"
            manifest.write_text(json.dumps({"episode_name": "Test"}), encoding="utf-8")
            # Falls back to count-based (1 manifest = episode 2).
            self.assertEqual(resolve_episode_number(Path(d)), 2)


class TestResolveEpisodeName(unittest.TestCase):
    def test_no_collision(self):
        with tempfile.TemporaryDirectory() as d:
            dt = datetime(2026, 3, 1, 12, 0, 0, tzinfo=ZoneInfo(TIMEZONE))
            name = resolve_episode_name(Path(d), now=dt)
            self.assertIn("March 1, 2026", name)

    def test_collision_adds_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            dt = datetime(2026, 3, 1, 12, 0, 0, tzinfo=ZoneInfo(TIMEZONE))
            # Create a conflict.
            base_name = build_episode_base_name(now=dt)
            (Path(d) / f"{base_name} - Manifest.json").write_text("{}", encoding="utf-8")
            name = resolve_episode_name(Path(d), now=dt)
            self.assertTrue(name.endswith("2"), f"Expected suffix '2', got: {name}")


class TestBuildArtifactPaths(unittest.TestCase):
    def test_all_keys_present(self):
        paths = build_artifact_paths(Path("/tmp/out"), "The Signal \u2013 March 1, 2026")
        for key in ("script_md", "script_json", "sources_json", "cover_png", "mp3", "manifest_json"):
            self.assertIn(key, paths)

    def test_paths_under_output_dir(self):
        out = Path("/tmp/out")
        paths = build_artifact_paths(out, "The Signal \u2013 March 1, 2026")
        for path in paths.values():
            self.assertTrue(str(path).startswith(str(out)))


if __name__ == "__main__":
    unittest.main()
