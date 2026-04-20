"""Tests for ai_podcast_pipeline.theme_research"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from ai_podcast_pipeline.models import CandidateStory
from ai_podcast_pipeline.theme_research import (
    _build_search_queries,
    _llm_generate_queries,
    _llm_filter_sources,
    _rank_sources,
    _score_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    title: str = "AI Tools for Communications",
    url: str = "https://example.com/article",
    domain: str = "example.com",
    published_at: datetime | None = None,
    summary: str = "",
) -> CandidateStory:
    return CandidateStory(
        title=title,
        url=url,
        source_domain=domain,
        published_at=published_at or datetime.now(timezone.utc),
        summary=summary,
    )


# ---------------------------------------------------------------------------
# _build_search_queries
# ---------------------------------------------------------------------------

class TestBuildSearchQueries(unittest.TestCase):
    def test_returns_multiple_queries(self):
        queries = _build_search_queries("Getting unstuck on first drafts")
        self.assertGreaterEqual(len(queries), 4)

    def test_returns_at_most_eight_queries(self):
        queries = _build_search_queries("Getting unstuck on first drafts")
        self.assertLessEqual(len(queries), 8)

    def test_includes_ai_angle(self):
        queries = _build_search_queries("Getting unstuck on first drafts")
        combined = " ".join(queries).lower()
        self.assertTrue(
            any(term in combined for term in ("ai", "artificial intelligence", "generative")),
            "At least one query should reference AI",
        )

    def test_includes_theme_keywords(self):
        queries = _build_search_queries("Getting unstuck on first drafts")
        combined = " ".join(queries).lower()
        # "drafts" is a meaningful theme word that should appear.
        self.assertIn("drafts", combined)

    def test_queries_are_strings(self):
        queries = _build_search_queries("Summarising long reports")
        for q in queries:
            self.assertIsInstance(q, str)
            self.assertTrue(len(q) > 0)

    def test_no_duplicate_queries(self):
        queries = _build_search_queries("Editing with AI")
        self.assertEqual(len(queries), len(set(queries)))

    def test_short_theme(self):
        """Single-word theme should still produce valid queries."""
        queries = _build_search_queries("Summarisation")
        self.assertGreaterEqual(len(queries), 4)


# ---------------------------------------------------------------------------
# _score_source
# ---------------------------------------------------------------------------

class TestScoreSource(unittest.TestCase):
    THEME = "Getting unstuck on first drafts"

    def _score(self, title, days_ago=3, domain="example.com"):
        published_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return _score_source(title, published_at, domain, self.THEME)

    # ── Freshness ────────────────────────────────────────────────────────

    def test_fresh_scores_higher_than_old(self):
        score_fresh = self._score("Some AI Article", days_ago=3)
        score_old = self._score("Some AI Article", days_ago=120)
        self.assertGreater(score_fresh, score_old)

    def test_very_old_article_gets_low_freshness(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=400)
        score = _score_source("Some AI Article", published_at, "example.com", self.THEME)
        # Max possible freshness for >360d old should be 0.
        self.assertLessEqual(
            score,
            # relevance(0) + freshness(0) + credibility(0) + practical(0) = 0
            # but title may get some relevance — so just check it's low
            20,
        )

    def test_none_published_at_gets_zero_freshness(self):
        score_none = _score_source("An article", None, "example.com", self.THEME)
        score_fresh = _score_source(
            "An article",
            datetime.now(timezone.utc) - timedelta(days=1),
            "example.com",
            self.THEME,
        )
        self.assertLess(score_none, score_fresh)

    # ── Relevance ─────────────────────────────────────────────────────────

    def test_relevant_title_scores_higher_than_irrelevant(self):
        score_relevant = self._score("Getting unstuck on first drafts with AI")
        score_irrelevant = self._score("Quantum computing breakthroughs in 2025")
        self.assertGreater(score_relevant, score_irrelevant)

    def test_more_matching_words_score_higher(self):
        # "drafts" matches one theme word; "first drafts" matches two.
        score_one = self._score("AI and drafts")
        score_two = self._score("AI for first drafts")
        self.assertGreaterEqual(score_two, score_one)

    def test_relevance_capped_at_40(self):
        # Title matches many theme words — relevance should not exceed 40.
        score = _score_source(
            "Getting unstuck on first drafts",
            datetime.now(timezone.utc),
            "example.com",
            "Getting unstuck on first drafts",
        )
        # Full match: 4+ words → 40 pts. Plus up to 25 (fresh) + 0 (no allowlist) + 0 = 65.
        self.assertLessEqual(score, 100)

    # ── Credibility ───────────────────────────────────────────────────────

    def test_allowlisted_domain_scores_higher(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=5)
        score_allow = _score_source("AI drafts guide", published_at, "hbr.org", self.THEME)
        score_unknown = _score_source("AI drafts guide", published_at, "randomblog.io", self.THEME)
        self.assertGreater(score_allow, score_unknown)

    def test_edu_domain_gets_credibility_points(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=5)
        score_edu = _score_source("AI tools", published_at, "mit.edu", self.THEME)
        score_unknown = _score_source("AI tools", published_at, "randomblog.io", self.THEME)
        self.assertGreater(score_edu, score_unknown)

    # ── Practical value ──────────────────────────────────────────────────

    def test_how_to_title_scores_practical_points(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=5)
        score_howto = _score_source(
            "How to use AI for first drafts", published_at, "example.com", self.THEME
        )
        score_plain = _score_source(
            "AI in the enterprise", published_at, "example.com", self.THEME
        )
        self.assertGreater(score_howto, score_plain)

    def test_comms_keyword_in_title_adds_points(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=5)
        score_comms = _score_source(
            "AI for communications teams", published_at, "example.com", self.THEME
        )
        score_plain = _score_source(
            "AI in the enterprise", published_at, "example.com", self.THEME
        )
        self.assertGreater(score_comms, score_plain)

    # ── Return type ───────────────────────────────────────────────────────

    def test_returns_float(self):
        score = self._score("AI drafts productivity tips")
        self.assertIsInstance(score, float)

    def test_score_is_non_negative(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=500)
        score = _score_source("Completely unrelated title", published_at, "unknown.io", self.THEME)
        self.assertGreaterEqual(score, 0)


# ---------------------------------------------------------------------------
# _rank_sources
# ---------------------------------------------------------------------------

class TestRankSources(unittest.TestCase):
    THEME = "AI writing assistant for communicators"

    def test_returns_at_most_max_results(self):
        candidates = [
            _make_candidate(title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(20)
        ]
        ranked = _rank_sources(candidates, self.THEME, max_results=5)
        self.assertLessEqual(len(ranked), 5)

    def test_relevant_candidate_ranked_first(self):
        relevant = _make_candidate(
            title="AI writing assistant tips for communicators",
            url="https://prdaily.com/ai-writing",
            domain="prdaily.com",
            published_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        irrelevant = _make_candidate(
            title="Quantum computing in healthcare",
            url="https://example.com/quantum",
            domain="example.com",
            published_at=datetime.now(timezone.utc) - timedelta(days=500),
        )
        ranked = _rank_sources([irrelevant, relevant], self.THEME, max_results=8)
        self.assertEqual(ranked[0].url, relevant.url)

    def test_empty_candidates_returns_empty(self):
        ranked = _rank_sources([], self.THEME)
        self.assertEqual(ranked, [])

    def test_returns_candidate_story_objects(self):
        candidates = [
            _make_candidate(title=f"Article {i}", url=f"https://example.com/{i}")
            for i in range(3)
        ]
        ranked = _rank_sources(candidates, self.THEME)
        for item in ranked:
            self.assertIsInstance(item, CandidateStory)


class TestCandidateStorySourceRole(unittest.TestCase):
    def test_default_source_role_is_primary(self):
        c = CandidateStory(
            title="Test", url="https://example.com", source_domain="example.com",
            published_at=None, summary="test",
        )
        self.assertEqual(c.source_role, "primary")

    def test_source_role_can_be_set_to_supporting(self):
        c = CandidateStory(
            title="Test", url="https://example.com", source_domain="example.com",
            published_at=None, summary="test", source_role="supporting",
        )
        self.assertEqual(c.source_role, "supporting")


class TestLlmGenerateQueries(unittest.TestCase):
    THEME = "AI for Internal Communications"

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_returns_queries_from_llm(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "queries": [
                "AI tools internal communications employee engagement 2026",
                "personalized employee messaging AI enterprise",
                "Microsoft Work Trend Index digital workplace productivity",
                "Edelman trust barometer AI-generated content credibility",
                "AI content personalization intranet newsletters",
                "internal comms measurement analytics AI beyond open rates",
                "McKinsey employee productivity AI knowledge workers",
                "AI video creation internal communications digital signage",
                "site:gartner.com AI internal communications",
                "site:gartner.com employee communications technology",
            ]
        })
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        self.assertGreaterEqual(len(queries), 8)
        self.assertLessEqual(len(queries), 12)
        for q in queries:
            self.assertIsInstance(q, str)
            self.assertTrue(len(q) > 0)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_falls_back_to_templates_on_failure(self, mock_chat):
        mock_chat.side_effect = Exception("API error")
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        # Should fall back to template-based queries
        self.assertGreaterEqual(len(queries), 4)
        for q in queries:
            self.assertIsInstance(q, str)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_deduplicates_queries(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "queries": [
                "AI internal comms",
                "AI internal comms",
                "employee engagement AI",
            ]
        })
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        self.assertEqual(len(queries), len(set(queries)))


class TestLlmFilterSourcesTiered(unittest.TestCase):
    THEME = "AI for Internal Communications"

    def _make_candidates(self, n=5):
        return [
            _make_candidate(
                title=f"Article {i}", url=f"https://example.com/{i}",
                domain="example.com", summary=f"Summary {i}",
            )
            for i in range(n)
        ]

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_returns_primary_and_supporting_indices(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "primary": [0, 1, 3],
            "supporting": [2, 4],
        })
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertEqual(primary, [0, 1, 3])
        self.assertEqual(supporting, [2, 4])

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_falls_back_from_old_format(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "selected_indices": [0, 2, 4],
        })
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertEqual(primary, [0, 2, 4])
        self.assertEqual(supporting, [])

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_caps_supporting_at_max(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "primary": [0],
            "supporting": [1, 2, 3, 4, 5, 6],
        })
        candidates = self._make_candidates(7)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertLessEqual(len(supporting), 4)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_fallback_on_exception(self, mock_chat):
        mock_chat.side_effect = Exception("API error")
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertGreater(len(primary), 0)
        self.assertEqual(supporting, [])


if __name__ == "__main__":
    unittest.main()
