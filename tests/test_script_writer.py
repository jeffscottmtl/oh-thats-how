"""Tests for ai_podcast_pipeline.script_writer"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_podcast_pipeline.constants import INTRO_TEXT, OUTRO_TEXT, ENDING_TOKEN
from ai_podcast_pipeline.models import CandidateStory, ScriptParts, ScoredStory
from ai_podcast_pipeline.script_writer import build_script_markdown, build_script_json
from ai_podcast_pipeline.utils import count_words


def _scored(title: str, domain: str = "venturebeat.com") -> ScoredStory:
    return ScoredStory(
        candidate=CandidateStory(
            title=title,
            url=f"https://{domain}/article",
            source_domain=domain,
            published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            summary="Summary text.",
        ),
        credibility=95,
        comms_relevance=60,
        freshness=80,
        ai_materiality=75,
        preferred_topic=50,
        total=75.0,
    )


def _parts(n: int) -> ScriptParts:
    return ScriptParts(
        story_narratives=[f"Narrative for story {i+1}." for i in range(n)],
        cn_relevance="This matters for CN teams.",
        food_for_thought="AI and human judgment work best together in communications.",
    )


class TestBuildScriptMarkdown(unittest.TestCase):
    def test_starts_with_intro(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        self.assertTrue(md.startswith(INTRO_TEXT))

    def test_ends_with_outro(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        self.assertIn(OUTRO_TEXT, md)

    def test_contains_one_more_thing_opener(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        self.assertIn("one more thing", md.lower())

    def test_no_story_labels(self):
        selected = [_scored("Story A"), _scored("Story B"), _scored("Story C")]
        parts = _parts(3)
        md = build_script_markdown(parts, selected)
        self.assertNotIn("Story 1:", md)
        self.assertNotIn("Story 2:", md)
        self.assertNotIn("Story 3:", md)

    def test_includes_all_narratives(self):
        selected = [_scored("Story A"), _scored("Story B")]
        parts = _parts(2)
        md = build_script_markdown(parts, selected)
        # _lc_first lowercases the first character of each narrative
        self.assertIn("narrative for story 1.", md)
        self.assertIn("narrative for story 2.", md)

    def test_cn_relevance_included_when_set(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        self.assertIn("This matters for CN teams.", md)

    def test_cn_relevance_omitted_when_none(self):
        selected = [_scored("Story A")]
        parts = ScriptParts(
            story_narratives=["Narrative."],
            cn_relevance=None,
            food_for_thought="Food.",
        )
        md = build_script_markdown(parts, selected)
        self.assertNotIn("This matters for CN teams.", md)

    def test_one_more_thing_before_outro(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        omt_pos = md.lower().index("one more thing")
        outro_pos = md.index(OUTRO_TEXT)
        self.assertLess(omt_pos, outro_pos)


class TestBuildScriptJson(unittest.TestCase):
    def test_story_count_matches(self):
        selected = [_scored("Story A"), _scored("Story B"), _scored("Story C")]
        parts = _parts(3)
        md = build_script_markdown(parts, selected)
        payload = build_script_json(parts, selected, md)
        self.assertEqual(len(payload["stories"]), 3)

    def test_word_count_populated(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        payload = build_script_json(parts, selected, md)
        self.assertGreater(payload["word_count"], 0)

    def test_stories_have_required_keys(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        payload = build_script_json(parts, selected, md)
        story = payload["stories"][0]
        for key in ("index", "title", "source_domain", "source_url", "published_at", "narrative"):
            self.assertIn(key, story)

    def test_ending_segment_key_present(self):
        selected = [_scored("Story A")]
        parts = _parts(1)
        md = build_script_markdown(parts, selected)
        payload = build_script_json(parts, selected, md)
        self.assertEqual(payload["ending_segment"], ENDING_TOKEN)


if __name__ == "__main__":
    unittest.main()
