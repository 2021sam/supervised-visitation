import unittest

from acquisition.extraction.supervisor_zip import extract_zip_code


class SupervisorZipTests(unittest.TestCase):

    def test_explicit_zip(self):
        self.assertEqual(
            extract_zip_code({"zip_code": "94506"}),
            "94506",
        )

    def test_address(self):
        self.assertEqual(
            extract_zip_code({"location": "Danville, CA 94506"}),
            "94506",
        )

    def test_full_california_name(self):
        self.assertEqual(
            extract_zip_code({"raw_text": "Bakersfield, California 93309"}),
            "93309",
        )

    def test_leading_zero(self):
        self.assertEqual(
            extract_zip_code({"raw_text": "Boston, MA 02108"}),
            "02108",
        )

    def test_zip_plus_four(self):
        self.assertEqual(
            extract_zip_code({"raw_text": "Danville, CA 94506-1234"}),
            "94506",
        )

    def test_multiple_zips(self):
        self.assertEqual(
            extract_zip_code({"raw_text": "CA 93285 and CA 93309"}),
            "93285",
        )

    def test_explicit_zip_priority(self):
        self.assertEqual(
            extract_zip_code({
                "zip_code": "94506",
                "raw_text": "CA 93309",
            }),
            "94506",
        )

    def test_unrelated_numbers(self):
        self.assertEqual(
            extract_zip_code({"raw_text": "License 12345, $100/hour"}),
            "",
        )

    def test_missing_zip(self):
        self.assertEqual(extract_zip_code({}), "")

    def test_service_area_not_zip(self):
        self.assertEqual(
            extract_zip_code({"service_area": "Orange County"}),
            "",
        )


if __name__ == "__main__":
    unittest.main()
