"""Regression tests for published website normalization."""

import unittest

from acquisition.extraction.provider_fields import normalize_website


class TestWebsiteNormalization(unittest.TestCase):

    def test_missing_values(self):
        for value in (None, "", "None", "N/A", "No Website"):
            with self.subTest(value=value):
                self.assertEqual(normalize_website(value), "")

    def test_missing_protocol(self):
        self.assertEqual(
            normalize_website("www.example.com"),
            "https://www.example.com",
        )

    def test_existing_https(self):
        self.assertEqual(
            normalize_website("https://example.com/services"),
            "https://example.com/services",
        )

    def test_existing_http(self):
        self.assertEqual(
            normalize_website("http://example.com"),
            "http://example.com",
        )

    def test_fragmented_domain(self):
        self.assertEqual(
            normalize_website("www .example.com"),
            "https://www.example.com",
        )

    def test_fragmented_path(self):
        self.assertEqual(
            normalize_website(
                "https://example.com/family - visitation/about - us"
            ),
            "https://example.com/family-visitation/about-us",
        )

    def test_escaped_underscore(self):
        self.assertEqual(
            normalize_website(
                r"https://example.com/family\_services"
            ),
            "https://example.com/family_services",
        )

    def test_email_not_website(self):
        self.assertEqual(
            normalize_website("contact@example.com"),
            "",
        )

    def test_unrelated_text(self):
        self.assertEqual(
            normalize_website("By appointment only"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
