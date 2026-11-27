import unittest

from acquisition.extraction.supervisor_service_area import (
    normalize_service_area,
)


class SupervisorServiceAreaTests(unittest.TestCase):

    def test_bullet_points(self):
        self.assertEqual(
            normalize_service_area("• Orange • Riverside • San Diego"),
            "Orange, Riverside, San Diego",
        )

    def test_preserve_order(self):
        self.assertEqual(
            normalize_service_area("Walnut Creek, Danville, Concord"),
            "Walnut Creek, Danville, Concord",
        )

    def test_county_name(self):
        self.assertEqual(
            normalize_service_area("Orange County"),
            "Orange County",
        )

    def test_semicolons(self):
        self.assertEqual(
            normalize_service_area("Walnut Creek; Danville"),
            "Walnut Creek, Danville",
        )

    def test_duplicate_areas(self):
        self.assertEqual(
            normalize_service_area("Danville, Concord, danville"),
            "Danville, Concord",
        )

    def test_whitespace(self):
        self.assertEqual(
            normalize_service_area("  San   Diego  "),
            "San Diego",
        )

    def test_html_entities(self):
        self.assertEqual(
            normalize_service_area("Orange &amp; Riverside"),
            "Orange & Riverside",
        )

    def test_newlines(self):
        self.assertEqual(
            normalize_service_area("Danville\nConcord"),
            "Danville, Concord",
        )

    def test_empty(self):
        self.assertEqual(normalize_service_area(""), "")

    def test_none(self):
        self.assertEqual(normalize_service_area(None), "")


if __name__ == "__main__":
    unittest.main()
