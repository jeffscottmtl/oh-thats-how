"""Tests for ai_podcast_pipeline.security"""
from __future__ import annotations

import unittest

from ai_podcast_pipeline.security import redact, scan_text_for_secrets


class TestRedact(unittest.TestCase):
    def test_redacts_openai_key_pattern(self):
        text = "key is sk-abcdefghijklmnopqrstuvwxyz1234567890"
        result = redact(text)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", result)
        self.assertIn("[REDACTED]", result)

    def test_redacts_api_key_assignment(self):
        text = 'api_key = "supersecretvalue1234567"'
        result = redact(text)
        self.assertIn("[REDACTED]", result)

    def test_clean_text_unchanged(self):
        text = "This is a normal podcast script with no secrets."
        self.assertEqual(redact(text), text)

    def test_redacts_token_pattern(self):
        text = "token: abcdef1234567890abcd"
        result = redact(text)
        self.assertIn("[REDACTED]", result)


class TestScanTextForSecrets(unittest.TestCase):
    def test_detects_openai_key(self):
        text = "My key is sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"
        self.assertTrue(scan_text_for_secrets(text))

    def test_clean_text_is_safe(self):
        text = "Today we cover AI and communications."
        self.assertFalse(scan_text_for_secrets(text))

    def test_detects_secret_assignment(self):
        text = 'secret="my_very_long_secret_value_1234"'
        self.assertTrue(scan_text_for_secrets(text))


if __name__ == "__main__":
    unittest.main()
