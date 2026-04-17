"""Tests for ai_podcast_pipeline.ingest"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ai_podcast_pipeline.ingest import _parse_feed, fetch_candidates


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>AI Tool Helps Comms Teams</title>
      <link>https://venturebeat.com/article-1</link>
      <description>Summary of the AI tool.</description>
      <pubDate>Mon, 01 Mar 2024 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Another Story</title>
      <link>https://techcrunch.com/article-2</link>
      <description>Tech story summary.</description>
      <pubDate>Mon, 01 Mar 2024 09:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
MALFORMED_RSS = "this is not xml <<<<"


class TestParseFeed(unittest.TestCase):
    def test_parses_items(self):
        stories = _parse_feed(SAMPLE_RSS)
        self.assertEqual(len(stories), 2)

    def test_titles_correct(self):
        stories = _parse_feed(SAMPLE_RSS)
        titles = [s.title for s in stories]
        self.assertIn("AI Tool Helps Comms Teams", titles)
        self.assertIn("Another Story", titles)

    def test_domains_extracted(self):
        stories = _parse_feed(SAMPLE_RSS)
        domains = {s.source_domain for s in stories}
        self.assertIn("venturebeat.com", domains)
        self.assertIn("techcrunch.com", domains)

    def test_dates_parsed(self):
        stories = _parse_feed(SAMPLE_RSS)
        self.assertIsNotNone(stories[0].published_at)

    def test_empty_feed_returns_empty_list(self):
        self.assertEqual(_parse_feed(EMPTY_RSS), [])

    def test_malformed_xml_returns_empty_list(self):
        self.assertEqual(_parse_feed(MALFORMED_RSS), [])

    def test_items_without_title_skipped(self):
        xml = """<rss><channel>
          <item><link>https://example.com/a</link></item>
        </channel></rss>"""
        stories = _parse_feed(xml)
        self.assertEqual(len(stories), 0)


class TestFetchCandidates(unittest.TestCase):
    @patch("ai_podcast_pipeline.ingest.requests.get")
    def test_returns_candidates_from_feeds(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = SAMPLE_RSS
        mock_get.return_value = mock_resp

        stories = fetch_candidates(feeds=["https://example.com/feed.rss"])
        self.assertGreater(len(stories), 0)

    @patch("ai_podcast_pipeline.ingest.requests.get")
    def test_deduplicates_across_feeds(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = SAMPLE_RSS
        mock_get.return_value = mock_resp

        # Same feed twice — should deduplicate.
        stories = fetch_candidates(
            feeds=["https://example.com/feed1.rss", "https://example.com/feed2.rss"]
        )
        urls = [s.url for s in stories]
        self.assertEqual(len(urls), len(set(urls)))

    @patch("ai_podcast_pipeline.ingest.Path.exists", return_value=False)
    @patch("ai_podcast_pipeline.ingest.requests.get")
    def test_failed_feed_skipped_gracefully(self, mock_get, _mock_exists):
        """When all feeds fail and no fallback file exists, return empty list."""
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException("timeout")
        stories = fetch_candidates(feeds=["https://example.com/feed.rss"])
        self.assertEqual(stories, [])


if __name__ == "__main__":
    unittest.main()
