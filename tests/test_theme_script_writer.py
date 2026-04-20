"""Tests for theme-based script generation."""
import unittest
import json
from unittest.mock import patch
from datetime import datetime, timezone

from ai_podcast_pipeline.models import CandidateStory, ScoredStory, ScriptParts
from ai_podcast_pipeline.script_writer import (
    generate_theme_script,
    build_theme_script_markdown,
)
from ai_podcast_pipeline.constants import INTRO_TEXT, OUTRO_TEXT


def _make_scored(title, summary, domain="wired.com", full_text="Full article content here."):
    c = CandidateStory(
        title=title, url=f"https://{domain}/art",
        source_domain=domain,
        published_at=datetime.now(timezone.utc),
        summary=summary, full_text=full_text,
    )
    return ScoredStory(candidate=c, credibility=90, comms_relevance=50,
                       freshness=80, ai_materiality=60, preferred_topic=0, total=55.0)


class TestBuildThemeScriptMarkdown(unittest.TestCase):
    def test_contains_intro_and_outro(self):
        parts = ScriptParts(
            theme_name="AI for first drafts",
            narrative="The body of the episode goes here.",
            try_this="Try giving AI three bullet points and asking for five openings.",
            food_for_thought="Here's a parting thought about drafts.",
        )
        md = build_theme_script_markdown(parts)
        self.assertIn(INTRO_TEXT, md)
        self.assertIn(OUTRO_TEXT, md)
        self.assertIn("The body of the episode goes here.", md)
        self.assertIn("Try giving AI three bullet points", md)
        self.assertIn("parting thought about drafts", md)

    def test_no_per_story_transitions(self):
        parts = ScriptParts(
            theme_name="test",
            narrative="One flowing narrative.",
            try_this="Try this thing.",
            food_for_thought="A thought.",
        )
        md = build_theme_script_markdown(parts)
        self.assertNotIn("To start,", md)
        self.assertNotIn("Next,", md)
        self.assertNotIn("And finally,", md)


class TestThemeArticlesBlobSourceRole(unittest.TestCase):
    def test_includes_source_role(self):
        from ai_podcast_pipeline.script_writer import _theme_articles_blob
        c = CandidateStory(
            title="Test Article", url="https://example.com/art",
            source_domain="example.com",
            published_at=datetime.now(timezone.utc),
            summary="A test article", full_text="Full text here.",
            source_role="supporting",
        )
        scored = ScoredStory(
            candidate=c, credibility=90, comms_relevance=50,
            freshness=80, ai_materiality=60, preferred_topic=0, total=55.0,
        )
        blob = _theme_articles_blob([scored])
        self.assertIn("role=supporting", blob)

    def test_primary_role_shown(self):
        from ai_podcast_pipeline.script_writer import _theme_articles_blob
        c = CandidateStory(
            title="Test Article", url="https://example.com/art",
            source_domain="example.com",
            published_at=datetime.now(timezone.utc),
            summary="A test article", full_text="Full text here.",
        )
        scored = ScoredStory(
            candidate=c, credibility=90, comms_relevance=50,
            freshness=80, ai_materiality=60, preferred_topic=0, total=55.0,
        )
        blob = _theme_articles_blob([scored])
        self.assertIn("role=primary", blob)


if __name__ == "__main__":
    unittest.main()
