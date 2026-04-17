"""Tests for ai_podcast_pipeline.verification"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from ai_podcast_pipeline.models import CandidateStory, ScoredStory
from ai_podcast_pipeline.verification import verify_story, _is_reachable_status


def _make_scored(
    domain: str = "techcrunch.com",
    published_at: datetime | None = None,
    url: str = "https://techcrunch.com/article",
) -> ScoredStory:
    return ScoredStory(
        candidate=CandidateStory(
            title="AI Story",
            url=url,
            source_domain=domain,
            published_at=published_at or datetime(2024, 3, 1, tzinfo=timezone.utc),
            summary="Summary.",
        ),
        credibility=95,
        comms_relevance=60,
        freshness=80,
        ai_materiality=75,
        preferred_topic=50,
        total=75.0,
    )


class TestIsReachableStatus(unittest.TestCase):
    def test_200_reachable(self):
        self.assertTrue(_is_reachable_status(200))

    def test_301_reachable(self):
        self.assertTrue(_is_reachable_status(301))

    def test_401_reachable(self):
        """401 is treated as reachable (bot-blocked publisher)."""
        self.assertTrue(_is_reachable_status(401))

    def test_403_reachable(self):
        """403 is treated as reachable (bot-blocked publisher)."""
        self.assertTrue(_is_reachable_status(403))

    def test_429_reachable(self):
        self.assertTrue(_is_reachable_status(429))

    def test_404_not_reachable(self):
        self.assertFalse(_is_reachable_status(404))

    def test_500_not_reachable(self):
        self.assertFalse(_is_reachable_status(500))


class TestVerifyStory(unittest.TestCase):
    APPROVED = {"techcrunch.com", "venturebeat.com"}

    def test_unapproved_domain_fails(self):
        story = _make_scored(domain="malicioussite.xyz")
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertFalse(result.passed)
        self.assertIn("Domain not approved", result.reason)

    def test_missing_date_fails(self):
        story = _make_scored(published_at=None)
        story.candidate.published_at = None
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertFalse(result.passed)
        self.assertIn("date", result.reason.lower())

    @patch("ai_podcast_pipeline.verification.requests.head")
    def test_reachable_url_passes(self, mock_head):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_head.return_value = mock_resp

        story = _make_scored()
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertTrue(result.passed)
        self.assertIsNone(result.reason)

    @patch("ai_podcast_pipeline.verification.requests.get")
    @patch("ai_podcast_pipeline.verification.requests.head")
    def test_fallback_to_get_when_head_fails(self, mock_head, mock_get):
        import requests as req_lib
        mock_head.side_effect = req_lib.RequestException("timeout")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        story = _make_scored()
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertTrue(result.passed)

    @patch("ai_podcast_pipeline.verification.requests.get")
    @patch("ai_podcast_pipeline.verification.requests.head")
    def test_404_from_both_fails(self, mock_head, mock_get):
        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 404
        mock_head.return_value = mock_head_resp
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 404
        mock_get.return_value = mock_get_resp

        story = _make_scored()
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertFalse(result.passed)
        self.assertIn("not reachable", result.reason)

    @patch("ai_podcast_pipeline.verification.requests.head")
    def test_403_publisher_block_passes(self, mock_head):
        """Bot-blocked publishers (403) should be treated as reachable."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_head.return_value = mock_resp

        story = _make_scored()
        result = verify_story(story, approved_domains=self.APPROVED)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
