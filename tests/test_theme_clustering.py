"""Tests for theme clustering."""
import unittest
import json
from unittest.mock import patch
from datetime import datetime, timezone

from ai_podcast_pipeline.models import CandidateStory, ScoredStory, ThemeCandidate
from ai_podcast_pipeline.theme_clustering import cluster_themes, _build_clustering_prompt


def _make_scored(title, summary, domain="techcrunch.com", idx=0):
    c = CandidateStory(
        title=title, url=f"https://{domain}/art{idx}",
        source_domain=domain, published_at=datetime.now(timezone.utc),
        summary=summary,
    )
    return ScoredStory(candidate=c, credibility=90, comms_relevance=50,
                       freshness=80, ai_materiality=60, preferred_topic=0, total=55.0)


class TestBuildClusteringPrompt(unittest.TestCase):
    def test_prompt_contains_all_titles(self):
        articles = [
            _make_scored("AI helps writers draft faster", "Tools for first drafts", idx=1),
            _make_scored("New Claude model released", "Anthropic ships update", idx=2),
        ]
        prompt = _build_clustering_prompt(articles)
        self.assertIn("AI helps writers draft faster", prompt)
        self.assertIn("New Claude model released", prompt)
        self.assertIn("communicators", prompt.lower())

    def test_prompt_includes_indices(self):
        articles = [_make_scored(f"Story {i}", f"Summary {i}", idx=i) for i in range(5)]
        prompt = _build_clustering_prompt(articles)
        self.assertIn("[1]", prompt)
        self.assertIn("[5]", prompt)


class TestClusterThemes(unittest.TestCase):
    @patch("ai_podcast_pipeline.theme_clustering.chat_completion")
    def test_parses_valid_response(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "themes": [
                {
                    "name": "AI for first drafts",
                    "description": "How AI helps communicators get past the blank page",
                    "article_indices": [1, 3],
                },
                {
                    "name": "Choosing the right AI tool",
                    "description": "What to look for when picking AI tools for content work",
                    "article_indices": [2, 4, 5],
                },
            ]
        })
        articles = [_make_scored(f"Story {i}", f"Summary {i}", idx=i) for i in range(5)]
        themes = cluster_themes(
            api_key="test", model="gpt-5.4-mini", scored_articles=articles,
        )
        self.assertEqual(len(themes), 2)
        self.assertEqual(themes[0].name, "AI for first drafts")
        self.assertEqual(themes[0].article_indices, [1, 3])
        self.assertIsInstance(themes[0], ThemeCandidate)


if __name__ == "__main__":
    unittest.main()
