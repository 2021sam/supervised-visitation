import unittest

from acquisition.extraction.supervisor_hourly_rate import (
    extract_hourly_rate,
)
from acquisition.extraction.supervisor_additional_info import (
    extract_additional_info,
)


class TestSupervisorHourlyRate(unittest.TestCase):

    def test_published_rates(self):
        cases = [
            ("Hourly Rate: $175.00", "$175.00 / hour"),
            ("Hourly: $75", "$75 / hour"),
            ("Hourly visits: $75", "$75 / hour"),
            ("Sliding scale: $15 - $140 / hour",
             "$15 - $140 / hour"),
            ("$100+ / hour", "$100+ / hour"),
            ("Hourly: starting at $75.00",
             "starting at $75.00 / hour"),
            ("Up to $150 / hour", "Up to $150 / hour"),
            ("Supervised\n\nVisits - $35/hr",
             "$35 / hour"),
            ("$60 / hour Exchanges $40 / hour",
             "$60 / hour"),
            ("$80 / hour $40 / hour for supervised exchanges",
             "$80 / hour"),
            ("Intake Fee / $120 / hour $120 / hour",
             "$120 / hour"),
            ("Intake fee: $50 Visit fee: $75 per hour",
             "$75 / hour"),
            ("Orientation: $50 per person", None),
            ("Exchanges: $40 / hour", None),
            ("$40 / hour for supervised exchanges", None),
            ("Intake fee: $100", None),
            ("", None),
        ]

        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    extract_hourly_rate(raw), expected
                )

    def test_explicit_hourly_range(self):
        result = extract_additional_info({
            "rates": "$60.00 - $90.00",
            "hourly_rate_labeled": True,
        })
        self.assertEqual(
            result,
            "Published rates: $60.00 - $90.00 / hour",
        )

    def test_raw_text_extraction(self):
        result = extract_additional_info({
            "raw_text": "Intake: $55 Hourly: $75",
        })
        self.assertEqual(
            result, "Published rates: $75 / hour"
        )

    def test_no_published_hourly_rate(self):
        result = extract_additional_info({
            "raw_text": "Orientation: $50 per person",
        })
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
