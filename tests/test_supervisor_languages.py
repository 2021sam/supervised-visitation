import unittest

from acquisition.extraction.supervisor_languages import (
    extract_languages,
)


class SupervisorLanguagesTests(unittest.TestCase):

    def test_structured_languages(self):
        self.assertEqual(
            extract_languages({"languages": "English, Spanish"}),
            "English, Spanish",
        )

    def test_structured_list(self):
        self.assertEqual(
            extract_languages({"languages": ["English", "Thai"]}),
            "English, Thai",
        )

    def test_bullet_points(self):
        self.assertEqual(
            extract_languages({
                "additional_info":
                    "• On-site visits • English, Spanish • Available daily"
            }),
            "English, Spanish",
        )

    def test_multilingual(self):
        self.assertEqual(
            extract_languages({
                "additional_info": "Multilingual (English, Spanish)"
            }),
            "English, Spanish",
        )

    def test_labeled_languages(self):
        self.assertEqual(
            extract_languages({
                "additional_info":
                    "Languages: English, Armenian, and Farsi"
            }),
            "English, Armenian, Farsi",
        )

    def test_html_entities(self):
        self.assertEqual(
            extract_languages({
                "additional_info": "English &amp; Spanish"
            }),
            "English, Spanish",
        )

    def test_referrals_excluded(self):
        self.assertEqual(
            extract_languages({
                "additional_info": "Spanish referrals available"
            }),
            "",
        )

    def test_duplicates(self):
        self.assertEqual(
            extract_languages({
                "additional_info": "• English, Spanish • English"
            }),
            "English, Spanish",
        )

    def test_structured_priority(self):
        self.assertEqual(
            extract_languages({
                "languages": "Thai",
                "additional_info": "English, Spanish",
            }),
            "Thai",
        )

    def test_missing_languages(self):
        self.assertEqual(extract_languages({}), "")


if __name__ == "__main__":
    unittest.main()
