import unittest

from acquisition.extraction.markdown_providers import extract_providers


class TestMarkdownProviderFields(unittest.TestCase):

    def test_phone_fax_labels(self):
        for label in ("Phone/Fax", "Phone/ Fax", "Phone / Fax", "Phone /Fax"):
            with self.subTest(label=label):
                markdown = f"""
| Example Provider | Example Provider |
| --- | --- |
| {label}: | 510-555-0100 / 510-555-0101 |
"""
                provider = extract_providers(markdown)[0]
                self.assertEqual(provider["phone"], "510-555-0100")

    def test_multiple_regular_phones(self):
        markdown = """
| Example Provider | Example Provider |
| --- | --- |
| Phone: | 510-555-0100 / 510-555-0101 |
"""
        provider = extract_providers(markdown)[0]
        self.assertEqual(
            provider["phone"],
            "510-555-0100 / 510-555-0101",
        )

    def test_preserve_published_rates(self):
        markdown = """
| Example Provider | Example Provider |
| --- | --- |
| Phone: | 510-555-0100 |
| Rate: | $75 - $125 per hour |
"""
        provider = extract_providers(markdown)[0]
        self.assertEqual(provider["rates"], "$75 - $125 per hour")

    def test_preserve_raw_text(self):
        markdown = """
| Example Provider | Example Provider |
| --- | --- |
| Phone/Fax: | 510-555-0100 / 510-555-0101 |
| Rate: | $75 per hour |
"""
        provider = extract_providers(markdown)[0]
        self.assertIn("Example Provider", provider["raw_text"])
        self.assertIn("510-555-0101", provider["raw_text"])
        self.assertIn("$75 per hour", provider["raw_text"])
