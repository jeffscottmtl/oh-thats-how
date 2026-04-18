"""Tests for ai_podcast_pipeline.theme_proposal."""
from __future__ import annotations

import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from ai_podcast_pipeline.models import ThemeBankEntry
from ai_podcast_pipeline.theme_proposal import (
    get_eligible_themes,
    load_theme_bank,
    mark_theme_used,
    save_theme_bank,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    id: str = "theme-001",
    name: str = "Test Theme",
    description: str = "A test theme",
    tags: list[str] | None = None,
    last_used: str | None = None,
    times_used: int = 0,
) -> ThemeBankEntry:
    return ThemeBankEntry(
        id=id,
        name=name,
        description=description,
        tags=tags or [],
        last_used=last_used,
        times_used=times_used,
    )


def _sample_bank() -> list[dict]:
    return [
        {
            "id": "theme-001",
            "name": "Writing with AI",
            "description": "Using AI to write first drafts faster",
            "tags": ["writing", "drafting"],
            "last_used": None,
            "times_used": 0,
        },
        {
            "id": "theme-002",
            "name": "Editing with AI",
            "description": "Using AI to tighten and polish copy",
            "tags": ["editing"],
            "last_used": "2025-01-01",
            "times_used": 3,
        },
    ]


# ---------------------------------------------------------------------------
# load_theme_bank
# ---------------------------------------------------------------------------

class TestLoadThemeBank(unittest.TestCase):
    def test_loads_valid_json(self, tmp_path=None):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "theme_bank.json"
            path.write_text(json.dumps(_sample_bank()), encoding="utf-8")
            entries = load_theme_bank(path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].id, "theme-001")
        self.assertEqual(entries[0].name, "Writing with AI")
        self.assertIsNone(entries[0].last_used)
        self.assertEqual(entries[0].times_used, 0)
        self.assertEqual(entries[1].id, "theme-002")
        self.assertEqual(entries[1].times_used, 3)

    def test_returns_empty_list_when_file_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nonexistent.json"
            entries = load_theme_bank(path)
        self.assertEqual(entries, [])

    def test_defaults_missing_optional_fields(self):
        """last_used and times_used default to None/0 when absent from JSON."""
        import tempfile
        minimal = [{"id": "t1", "name": "Minimal", "description": "Desc"}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bank.json"
            path.write_text(json.dumps(minimal), encoding="utf-8")
            entries = load_theme_bank(path)
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0].last_used)
        self.assertEqual(entries[0].times_used, 0)
        self.assertEqual(entries[0].tags, [])


# ---------------------------------------------------------------------------
# save_theme_bank
# ---------------------------------------------------------------------------

class TestSaveThemeBank(unittest.TestCase):
    def test_writes_valid_json(self):
        import tempfile
        entries = [_make_entry("theme-001", times_used=2, last_used="2025-03-01")]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bank.json"
            save_theme_bank(path, entries)
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], "theme-001")
        self.assertEqual(payload[0]["times_used"], 2)
        self.assertEqual(payload[0]["last_used"], "2025-03-01")

    def test_creates_parent_directories(self):
        import tempfile
        entries = [_make_entry()]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "deep" / "bank.json"
            save_theme_bank(path, entries)
            self.assertTrue(path.exists())

    def test_roundtrip(self):
        """load → save → load should produce identical entries."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bank.json"
            path.write_text(json.dumps(_sample_bank()), encoding="utf-8")
            original = load_theme_bank(path)
            save_theme_bank(path, original)
            reloaded = load_theme_bank(path)
        self.assertEqual(len(reloaded), len(original))
        for orig, rel in zip(original, reloaded):
            self.assertEqual(orig.id, rel.id)
            self.assertEqual(orig.name, rel.name)
            self.assertEqual(orig.last_used, rel.last_used)
            self.assertEqual(orig.times_used, rel.times_used)

    def test_saves_empty_list(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bank.json"
            save_theme_bank(path, [])
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload, [])


# ---------------------------------------------------------------------------
# mark_theme_used
# ---------------------------------------------------------------------------

class TestMarkThemeUsed(unittest.TestCase):
    def test_sets_last_used_to_today(self):
        entries = [_make_entry("t1")]
        mark_theme_used(entries, "t1")
        self.assertEqual(entries[0].last_used, date.today().isoformat())

    def test_increments_times_used(self):
        entries = [_make_entry("t1", times_used=4)]
        mark_theme_used(entries, "t1")
        self.assertEqual(entries[0].times_used, 5)

    def test_increments_from_zero(self):
        entries = [_make_entry("t1", times_used=0)]
        mark_theme_used(entries, "t1")
        self.assertEqual(entries[0].times_used, 1)

    def test_noop_on_missing_id(self):
        entries = [_make_entry("t1", times_used=2)]
        mark_theme_used(entries, "t999")  # should not raise
        self.assertEqual(entries[0].times_used, 2)
        self.assertIsNone(entries[0].last_used)

    def test_only_updates_matching_entry(self):
        entries = [_make_entry("t1"), _make_entry("t2", times_used=10)]
        mark_theme_used(entries, "t1")
        self.assertEqual(entries[0].last_used, date.today().isoformat())
        self.assertEqual(entries[0].times_used, 1)
        # t2 should be untouched
        self.assertIsNone(entries[1].last_used)
        self.assertEqual(entries[1].times_used, 10)


# ---------------------------------------------------------------------------
# get_eligible_themes
# ---------------------------------------------------------------------------

class TestGetEligibleThemes(unittest.TestCase):
    COOLDOWN = 30  # days

    def _days_ago(self, n: int) -> str:
        return (date.today() - timedelta(days=n)).isoformat()

    def test_never_used_is_eligible(self):
        entries = [_make_entry("t1", last_used=None)]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "t1")

    def test_used_today_is_not_eligible(self):
        entries = [_make_entry("t1", last_used=date.today().isoformat())]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(result, [])

    def test_used_within_cooldown_is_not_eligible(self):
        entries = [_make_entry("t1", last_used=self._days_ago(15))]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(result, [])

    def test_used_exactly_at_cooldown_boundary_is_eligible(self):
        """A theme used exactly COOLDOWN_DAYS ago should be eligible."""
        entries = [_make_entry("t1", last_used=self._days_ago(self.COOLDOWN))]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(len(result), 1)

    def test_used_beyond_cooldown_is_eligible(self):
        entries = [_make_entry("t1", last_used=self._days_ago(60))]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(len(result), 1)

    def test_mixed_entries(self):
        entries = [
            _make_entry("t1", last_used=None),           # never used — eligible
            _make_entry("t2", last_used=self._days_ago(5)),   # too recent
            _make_entry("t3", last_used=self._days_ago(31)),  # past cooldown — eligible
            _make_entry("t4", last_used=self._days_ago(30)),  # exactly at boundary — eligible
        ]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        ids = {e.id for e in result}
        self.assertIn("t1", ids)
        self.assertNotIn("t2", ids)
        self.assertIn("t3", ids)
        self.assertIn("t4", ids)

    def test_empty_bank_returns_empty(self):
        result = get_eligible_themes([], cooldown_days=self.COOLDOWN)
        self.assertEqual(result, [])

    def test_invalid_last_used_date_treated_as_eligible(self):
        """Entries with a malformed date string should be included, not crash."""
        entries = [_make_entry("t1", last_used="not-a-date")]
        result = get_eligible_themes(entries, cooldown_days=self.COOLDOWN)
        self.assertEqual(len(result), 1)

    def test_custom_cooldown(self):
        entries = [
            _make_entry("t1", last_used=self._days_ago(10)),
            _make_entry("t2", last_used=self._days_ago(10)),
        ]
        # With cooldown=7, 10 days ago is past — both eligible.
        result_short = get_eligible_themes(entries, cooldown_days=7)
        self.assertEqual(len(result_short), 2)
        # With cooldown=30, 10 days ago is recent — none eligible.
        result_long = get_eligible_themes(entries, cooldown_days=30)
        self.assertEqual(len(result_long), 0)


if __name__ == "__main__":
    unittest.main()
