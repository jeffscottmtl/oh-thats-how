"""Tests for pipeline date-window and source-cap filtering logic."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from ai_podcast_pipeline.models import CandidateStory, ScoredStory
from ai_podcast_pipeline.pipeline import (
    _apply_weekly_per_source_cap,
    _filter_by_date_window,
)


def _story(domain: str = "techcrunch.com", day: int = 1, month: int = 3, year: int = 2024) -> ScoredStory:
    published = datetime(year, month, day, tzinfo=timezone.utc)
    return ScoredStory(
        candidate=CandidateStory(
            title=f"Story from {domain} on {year}-{month}-{day}",
            url=f"https://{domain}/story-{day}",
            source_domain=domain,
            published_at=published,
            summary="",
        ),
        credibility=95,
        comms_relevance=60,
        freshness=80,
        ai_materiality=75,
        preferred_topic=50,
        total=75.0,
    )


class TestFilterByDateWindow(unittest.TestCase):
    def test_keeps_in_range(self):
        items = [_story(day=5)]
        kept, dropped = _filter_by_date_window(
            items, date(2024, 3, 1), date(2024, 3, 10)
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 0)

    def test_drops_out_of_range(self):
        items = [_story(day=15)]
        kept, dropped = _filter_by_date_window(
            items, date(2024, 3, 1), date(2024, 3, 10)
        )
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(dropped), 1)

    def test_inclusive_boundaries(self):
        items = [_story(day=1), _story(day=10), _story(day=11)]
        kept, dropped = _filter_by_date_window(
            items, date(2024, 3, 1), date(2024, 3, 10)
        )
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(dropped), 1)

    def test_no_date_dropped(self):
        story = _story()
        story.candidate.published_at = None
        kept, dropped = _filter_by_date_window(
            [story], date(2024, 3, 1), date(2024, 3, 10)
        )
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(dropped), 1)


class TestApplyWeeklyPerSourceCap(unittest.TestCase):
    def test_caps_at_limit(self):
        # 4 stories from same domain in same week → max 3 kept.
        items = [_story("techcrunch.com", day=i) for i in range(1, 5)]
        kept, dropped = _apply_weekly_per_source_cap(items, max_per_source=3)
        self.assertEqual(len(kept), 3)
        self.assertEqual(dropped, 1)

    def test_allows_up_to_limit(self):
        items = [_story("techcrunch.com", day=i) for i in range(1, 4)]
        kept, dropped = _apply_weekly_per_source_cap(items, max_per_source=3)
        self.assertEqual(len(kept), 3)
        self.assertEqual(dropped, 0)

    def test_different_domains_not_capped(self):
        items = [
            _story("techcrunch.com", day=1),
            _story("techcrunch.com", day=2),
            _story("venturebeat.com", day=3),
            _story("venturebeat.com", day=4),
        ]
        kept, dropped = _apply_weekly_per_source_cap(items, max_per_source=2)
        self.assertEqual(len(kept), 4)
        self.assertEqual(dropped, 0)

    def test_stories_in_different_weeks_both_allowed(self):
        # Same domain but two stories in different weeks — both should be kept.
        items = [
            _story("techcrunch.com", day=1, month=3),   # week of Feb 26
            _story("techcrunch.com", day=2, month=3),   # same week
            _story("techcrunch.com", day=3, month=3),   # same week
            _story("techcrunch.com", day=10, month=3),  # different week
        ]
        kept, dropped = _apply_weekly_per_source_cap(items, max_per_source=3)
        # 3 from first week + 1 from second week = 4 total.
        self.assertEqual(len(kept), 4)
        self.assertEqual(dropped, 0)

    def test_invalid_max_raises(self):
        with self.assertRaises(ValueError):
            _apply_weekly_per_source_cap([], max_per_source=0)


if __name__ == "__main__":
    unittest.main()
