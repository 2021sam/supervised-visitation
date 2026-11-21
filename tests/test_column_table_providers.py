import unittest

from acquisition.extraction.column_table_providers import (
    extract_column_table_providers,
)


class ColumnTableProviderTests(unittest.TestCase):

    def test_separate_providers_not_merged(self):
        markdown = """
| Name and Contact Information | Email | Services Offered | Website |
| --- | --- | --- | --- |
| Jane Smith | jane@example.com | Supervised visitation | |
| John Williams | john@example.com | Supervised visitation | |
"""
        providers = extract_column_table_providers(markdown)

        self.assertEqual(len(providers), 2)


if __name__ == "__main__":
    unittest.main()
