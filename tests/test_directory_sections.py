"""Regression tests for provider directory section isolation."""

import unittest

from acquisition.extraction.directory_sections import (
    has_provider_directory_heading,
    isolate_provider_tables,
)


PROVIDER_TABLE = """| SUPERVISED VISITATION PROVIDERS | SUPERVISED VISITATION PROVIDERS |
|---|---|
| Jane Smith 415-555-0101 | John Williams 415-555-0102 |"""

SECOND_TABLE = """| SUPERVISED VISITATION PROVIDERS | SUPERVISED VISITATION PROVIDERS |
|---|---|
| Mary Jones 415-555-0103 | |"""

UNRELATED_TABLE = """| LEGAL SERVICES | LEGAL SERVICES |
|---|---|
| Legal Aid 415-555-0104 | Counseling 415-555-0105 |"""


class TestDirectorySections(unittest.TestCase):

    def test_isolate_single_provider_table(self):
        self.assertEqual(
            isolate_provider_tables(PROVIDER_TABLE),
            PROVIDER_TABLE,
        )

    def test_exclude_unrelated_table(self):
        markdown = UNRELATED_TABLE + "\n\n" + PROVIDER_TABLE
        self.assertEqual(
            isolate_provider_tables(markdown),
            PROVIDER_TABLE,
        )

    def test_preserve_multiple_provider_tables(self):
        markdown = "\n\n".join([
            PROVIDER_TABLE,
            UNRELATED_TABLE,
            SECOND_TABLE,
        ])
        self.assertEqual(
            isolate_provider_tables(markdown),
            PROVIDER_TABLE + "\n\n" + SECOND_TABLE,
        )

    def test_no_provider_tables(self):
        self.assertEqual(
            isolate_provider_tables(UNRELATED_TABLE),
            "",
        )

    def test_exclude_unrelated_heading(self):
        markdown = (
            "## Community Resources\n\n"
            "Counseling 415-555-0106\n\n"
            + PROVIDER_TABLE
        )
        self.assertEqual(
            isolate_provider_tables(markdown),
            PROVIDER_TABLE,
        )

    def test_preserve_heading_detection(self):
        self.assertTrue(
            has_provider_directory_heading(
                "## Professional Supervised Visitation Providers"
            )
        )

    def test_reject_unrelated_heading(self):
        self.assertFalse(
            has_provider_directory_heading(
                "## Parenting Education"
            )
        )

    def test_heading_only_directory_not_a_table(self):
        markdown = (
            "## Professional Supervised Visitation Providers\n\n"
            "### Jane Smith\n"
            "415-555-0101"
        )
        self.assertTrue(
            has_provider_directory_heading(markdown)
        )
        self.assertEqual(
            isolate_provider_tables(markdown),
            "",
        )


if __name__ == "__main__":
    unittest.main()
