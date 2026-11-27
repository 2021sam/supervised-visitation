import unittest

from acquisition.extraction.label_value_providers import (
    extract_label_value_providers,
)


class TestLabelValueProviders(unittest.TestCase):

    def test_inline_fields(self):
        records = extract_label_value_providers("""
Name of Provider: Jane Smith
Email: jane@example.com
Phone: (415) 555-0101
""")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Jane Smith")
        self.assertEqual(records[0]["email"], "jane@example.com")
        self.assertEqual(records[0]["phone"], "(415) 555-0101")

    def test_separate_lines(self):
        records = extract_label_value_providers("""
Name of Provider:

Jane Smith

Email:

jane@example.com

Phone:

(415) 555-0101

Name of Provider:

John Smith

Email:

john@example.com

Phone:

(415) 555-0102
""")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["name"], "Jane Smith")
        self.assertEqual(records[1]["name"], "John Smith")
        self.assertEqual(records[1]["email"], "john@example.com")

    def test_multiline_name(self):
        records = extract_label_value_providers("""
Name of Provider:

Example Visitation Services,
Jane Smith

Email:

jane@example.com
""")
        self.assertEqual(
            records[0]["name"],
            "Example Visitation Services, Jane Smith",
        )

    def test_separate_colon(self):
        records = extract_label_value_providers("""
Name of Provider:

Jane Smith

Intake &amp; Report Fees

:

$100
""")
        self.assertEqual(
            records[0]["intake_report_fees"], "$100"
        )

    def test_multiline_phone(self):
        records = extract_label_value_providers("""
Name of Provider:

Jane Smith

Phone: (

415) 555-0101
""")
        self.assertEqual(
            records[0]["phone"], "( 415) 555-0101"
        )


if __name__ == "__main__":
    unittest.main()
