import unittest

from acquisition.extraction.heading_providers import (
    extract_heading_providers,
)


class TestHeadingProviders(unittest.TestCase):

    def test_exclude_directory_headings(self):
        markdown = """
## Professional Supervised Visitation and Exchange Provider List
510-555-0100

## Professional Supervised Visitation and Exchange Provider List Cont'd
510-555-0101

## Example Visitation Services
510-555-0102
"""
        providers = extract_heading_providers(markdown)

        self.assertEqual(len(providers), 1)
        self.assertEqual(
            providers[0]["name"],
            "Example Visitation Services",
        )
