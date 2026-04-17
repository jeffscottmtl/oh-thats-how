"""Tests for ai_podcast_pipeline.utils"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from ai_podcast_pipeline.utils import (
    canonical_domain,
    canonical_url,
    count_words,
    parse_datetime,
    parse_indices,
)


class TestCanonicalDomain(unittest.TestCase):
    def test_strips_www(self):
        self.assertEqual(canonical_domain("https://www.nytimes.com/article"), "nytimes.com")

    def test_no_www(self):
        self.assertEqual(canonical_domain("https://techcrunch.com/post"), "techcrunch.com")

    def test_lowercases(self):
        self.assertEqual(canonical_domain("https://BBC.CO.UK/news"), "bbc.co.uk")


class TestCanonicalUrl(unittest.TestCase):
    def test_strips_www(self):
        url = canonical_url("https://www.nytimes.com/2024/article")
        self.assertNotIn("www.", url)

    def test_preserves_path(self):
        url = canonical_url("https://techcrunch.com/2024/01/01/some-story/")
        self.assertIn("/2024/01/01/some-story/", url)

    def test_strips_utm_params(self):
        url = canonical_url("https://example.com/article?utm_source=twitter&utm_medium=social")
        self.assertNotIn("utm_source", url)
        self.assertNotIn("utm_medium", url)

    def test_preserves_functional_query_params(self):
        """Functional query params (e.g. article IDs) must be preserved."""
        url = canonical_url("https://news.google.com/rss/articles/CBMiVA?hl=en-US&gl=US&ceid=US:en")
        self.assertIn("hl=en-US", url)

    def test_strips_only_tracking_preserves_others(self):
        url = canonical_url("https://example.com/page?id=123&utm_campaign=spring&ref=home")
        self.assertIn("id=123", url)
        self.assertNotIn("utm_campaign", url)
        self.assertNotIn("ref=", url)

    def test_no_query_string(self):
        url = canonical_url("https://openai.com/blog/post")
        self.assertEqual(url, "https://openai.com/blog/post")

    def test_lowercases_scheme_and_host(self):
        url = canonical_url("HTTPS://WWW.BBC.CO.UK/news")
        self.assertTrue(url.startswith("https://bbc.co.uk"))


class TestParseDatetime(unittest.TestCase):
    def test_iso8601(self):
        dt = parse_datetime("2024-03-15T10:30:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_rfc2822(self):
        dt = parse_datetime("Mon, 15 Mar 2024 10:30:00 +0000")
        self.assertIsNotNone(dt)

    def test_none_input(self):
        self.assertIsNone(parse_datetime(None))

    def test_empty_string(self):
        self.assertIsNone(parse_datetime(""))

    def test_garbage(self):
        self.assertIsNone(parse_datetime("not a date"))

    def test_iso_without_tz_gets_utc(self):
        dt = parse_datetime("2024-03-15T10:30:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)


class TestCountWords(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(count_words("Hello world"), 2)

    def test_hyphenated(self):
        # Hyphenated words count as one token.
        self.assertEqual(count_words("state-of-the-art"), 1)

    def test_empty(self):
        self.assertEqual(count_words(""), 0)

    def test_newlines(self):
        self.assertEqual(count_words("one\ntwo\nthree"), 3)


class TestParseIndices(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_indices("1,3,5", 10), [1, 3, 5])

    def test_deduplicates(self):
        self.assertEqual(parse_indices("2,2,3", 10), [2, 3])

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            parse_indices("11", 10)

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            parse_indices("0", 5)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_indices("", 5)

    def test_non_integer_raises(self):
        with self.assertRaises(ValueError):
            parse_indices("a", 5)

    def test_preserves_order(self):
        self.assertEqual(parse_indices("5,2,8", 10), [5, 2, 8])


if __name__ == "__main__":
    unittest.main()
