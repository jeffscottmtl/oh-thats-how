"""Tests for theme-based models."""
import unittest
from ai_podcast_pipeline.models import ThemeCandidate, ScriptParts


class TestThemeCandidate(unittest.TestCase):
    def test_create_theme_candidate(self):
        tc = ThemeCandidate(
            name="Getting unstuck on first drafts",
            description="How AI can help communicators break through writer's block",
            article_indices=[3, 7, 12],
        )
        self.assertEqual(tc.name, "Getting unstuck on first drafts")
        self.assertEqual(len(tc.article_indices), 3)

    def test_script_parts_theme_fields(self):
        parts = ScriptParts(
            theme_name="Getting unstuck on first drafts",
            narrative="Full episode narrative here.",
            try_this="Next time you're stuck, try giving AI three bullet points...",
            food_for_thought="Here's some food for thought. I've been thinking...",
        )
        self.assertEqual(parts.theme_name, "Getting unstuck on first drafts")
        self.assertIsNotNone(parts.try_this)
        self.assertIsNone(parts.cn_relevance)


if __name__ == "__main__":
    unittest.main()
