"""Tests for ai_podcast_pipeline.scoring"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from ai_podcast_pipeline.models import CandidateStory, ScoredStory
from ai_podcast_pipeline.scoring import (
    ai_materiality_score,
    comms_relevance_score,
    credibility_score,
    freshness_score,
    is_excluded,
    is_relevant_story,
    preferred_topic_score,
    score_story,
    story_sort_key,
)


def _make_story(
    title: str = "AI Tool Helps Communications Teams",
    summary: str = "An AI workflow automation tool for communications professionals.",
    domain: str = "venturebeat.com",
    published_at: datetime | None = None,
) -> CandidateStory:
    if published_at is None:
        published_at = datetime.now(timezone.utc)
    return CandidateStory(
        title=title,
        url=f"https://{domain}/article",
        source_domain=domain,
        published_at=published_at,
        summary=summary,
    )


class TestCredibilityScore(unittest.TestCase):
    def test_allowlisted_domain(self):
        story = _make_story(domain="venturebeat.com")
        self.assertEqual(credibility_score(story), 95)

    def test_edu_domain(self):
        story = _make_story(domain="mit.edu")
        self.assertEqual(credibility_score(story), 80)

    def test_org_domain(self):
        story = _make_story(domain="eff.org")
        self.assertEqual(credibility_score(story), 80)

    def test_unknown_domain(self):
        story = _make_story(domain="randomsite.xyz")
        self.assertEqual(credibility_score(story), 70)


class TestFreshnessScore(unittest.TestCase):
    def _now(self):
        return datetime.now(timezone.utc)

    def test_very_fresh(self):
        story = _make_story(published_at=self._now() - timedelta(hours=6))
        self.assertEqual(freshness_score(story, now=self._now()), 100)

    def test_two_days_old(self):
        story = _make_story(published_at=self._now() - timedelta(days=2))
        self.assertEqual(freshness_score(story, now=self._now()), 90)

    def test_one_week_old(self):
        story = _make_story(published_at=self._now() - timedelta(days=6))
        self.assertEqual(freshness_score(story, now=self._now()), 80)

    def test_three_weeks_old(self):
        story = _make_story(published_at=self._now() - timedelta(days=21))
        self.assertEqual(freshness_score(story, now=self._now()), 40)

    def test_very_old(self):
        story = _make_story(published_at=self._now() - timedelta(days=90))
        self.assertEqual(freshness_score(story, now=self._now()), 20)

    def test_no_date(self):
        story = _make_story()
        story.published_at = None
        self.assertEqual(freshness_score(story), 30)


class TestAiMaterialityScore(unittest.TestCase):
    def test_high_ai_score(self):
        story = _make_story(
            title="New AI LLM Model Released",
            summary="A generative AI chatbot uses machine learning for enterprise automation.",
        )
        score = ai_materiality_score(story)
        self.assertGreater(score, 50)

    def test_low_ai_score(self):
        story = _make_story(title="Quarterly Earnings Report", summary="Revenue grew 5%.")
        score = ai_materiality_score(story)
        self.assertEqual(score, 0)

    def test_caps_at_100(self):
        story = _make_story(
            title="AI AI AI LLM AI generative",
            summary="AI AI AI AI AI AI AI machine learning AI model",
        )
        self.assertLessEqual(ai_materiality_score(story), 100)


class TestCommsRelevanceScore(unittest.TestCase):
    def test_comms_heavy(self):
        story = _make_story(
            title="AI Transforms PR and Corporate Communications",
            summary="Public relations and media relations teams use AI for press releases.",
        )
        score = comms_relevance_score(story)
        self.assertGreater(score, 40)

    def test_no_comms(self):
        story = _make_story(title="New GPU Released", summary="Faster chip for gaming.")
        self.assertEqual(comms_relevance_score(story), 0)


class TestIsExcluded(unittest.TestCase):
    def test_politics_excluded(self):
        story = _make_story(title="Congress debates AI legislation", summary="Senate hearing on AI policy.")
        self.assertTrue(is_excluded(story))

    def test_gaming_excluded(self):
        story = _make_story(title="Nintendo Switch 2 Review", summary="Hands-on with the new console.")
        self.assertTrue(is_excluded(story))

    def test_relevant_not_excluded(self):
        story = _make_story(
            title="AI Copilot for Communications Teams",
            summary="Workflow automation for PR professionals.",
        )
        self.assertFalse(is_excluded(story))


class TestIsRelevantStory(unittest.TestCase):
    def test_strong_ai_comms_story_passes(self):
        story = _make_story(
            title="AI Copilot Transforms Communications Workflow",
            summary="Enterprise AI assistant automates PR communications for teams.",
            domain="venturebeat.com",
        )
        scored = score_story(story)
        self.assertTrue(is_relevant_story(scored))

    def test_consumer_gadget_fails(self):
        # Use a domain not in AI_FOCUSED_DOMAINS so domain authority can't
        # override the lack of AI/comms signal.
        story = _make_story(
            title="Best Earbuds Under $50",
            summary="We review the top earbuds from Samsung and Apple.",
            domain="consumerreports.org",
        )
        scored = score_story(story)
        self.assertFalse(is_relevant_story(scored))

    def test_broad_gate_catches_ai_outlet_story(self):
        story = _make_story(
            title="OpenAI Updates Enterprise Policies",
            summary="Business customers gain new tools for their teams.",
            domain="openai.com",
        )
        scored = score_story(story)
        self.assertTrue(is_relevant_story(scored))


class TestStorySortKey(unittest.TestCase):
    def test_higher_total_ranks_first(self):
        now = datetime.now(timezone.utc)
        story_a = _make_story(title="A", published_at=now)
        story_b = _make_story(title="B", published_at=now)
        scored_a = score_story(story_a)
        scored_b = score_story(story_b)
        # Force different totals.
        object.__setattr__(scored_a, "total", 80.0)
        object.__setattr__(scored_b, "total", 60.0)
        self.assertLess(story_sort_key(scored_a), story_sort_key(scored_b))

    def test_newer_story_ranks_first_on_equal_total(self):
        older = _make_story(published_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
        newer = _make_story(published_at=datetime(2024, 3, 1, tzinfo=timezone.utc))
        scored_older = score_story(older)
        scored_newer = score_story(newer)
        object.__setattr__(scored_older, "total", 70.0)
        object.__setattr__(scored_newer, "total", 70.0)
        self.assertLess(story_sort_key(scored_newer), story_sort_key(scored_older))


if __name__ == "__main__":
    unittest.main()
