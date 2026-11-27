import unittest

from acquisition.extraction.supervisor_additional_info import (
    extract_additional_info,
)


class SupervisorAdditionalInfoTests(unittest.TestCase):

    def test_additional_info(self):
        self.assertEqual(
            extract_additional_info({
                "additional_info": "Available on weekends"
            }),
            "Available on weekends",
        )

    def test_rates(self):
        self.assertEqual(
            extract_additional_info({"rates": "$100/hour"}),
            "Published rates: $100/hour",
        )

    def test_availability(self):
        self.assertEqual(
            extract_additional_info({"availability": "Monday-Friday"}),
            "Availability: Monday-Friday",
        )

    def test_services(self):
        self.assertEqual(
            extract_additional_info({"services": "Minor transport"}),
            "Services: Minor transport",
        )

    def test_trustline(self):
        self.assertEqual(
            extract_additional_info({"trustline": "Registered"}),
            "TrustLine: Registered",
        )

    def test_combined_fields(self):
        self.assertEqual(
            extract_additional_info({
                "additional_info": "CPR certified",
                "rates": "$100/hour",
                "availability": "Weekends",
            }),
            "CPR certified\n"
            "Published rates: $100/hour\n"
            "Availability: Weekends",
        )

    def test_duplicates(self):
        self.assertEqual(
            extract_additional_info({
                "additional_info": "Available daily",
                "availability": "Available daily",
            }),
            "Available daily",
        )

    def test_whitespace_and_html(self):
        self.assertEqual(
            extract_additional_info({
                "additional_info": "  CPR  &amp;  First Aid  "
            }),
            "CPR & First Aid",
        )

    def test_raw_text_excluded(self):
        self.assertEqual(
            extract_additional_info({
                "raw_text": "Unverified document content"
            }),
            "",
        )

    def test_empty(self):
        self.assertEqual(extract_additional_info({}), "")


if __name__ == "__main__":
    unittest.main()
