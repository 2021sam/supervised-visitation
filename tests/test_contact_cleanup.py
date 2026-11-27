"""Regression tests for provider phone normalization."""

import unittest

from acquisition.extraction.contact_cleanup import (
    normalize_phone_numbers,
)


class TestPhoneNormalization(unittest.TestCase):

    def test_multiple_numbers(self):
        self.assertEqual(
            normalize_phone_numbers(
                "(888) 277- 7747 (415) 353 -6595"
            ),
            "(888) 277-7747; (415) 353-6595",
        )

    def test_fragmented_number(self):
        self.assertEqual(
            normalize_phone_numbers("( 510) 394 - 3911"),
            "(510) 394-3911",
        )

    def test_country_code(self):
        self.assertEqual(
            normalize_phone_numbers("+1 650-504-5107"),
            "(650) 504-5107",
        )

    def test_digits_only(self):
        self.assertEqual(
            normalize_phone_numbers("6505045107"),
            "(650) 504-5107",
        )

    def test_duplicates(self):
        self.assertEqual(
            normalize_phone_numbers(
                "(650) 504-5107; 650-504-5107"
            ),
            "(650) 504-5107",
        )

    def test_multiple_arguments(self):
        self.assertEqual(
            normalize_phone_numbers(
                "888-277-7747", "415-353-6595"
            ),
            "(888) 277-7747; (415) 353-6595",
        )

    def test_missing_values(self):
        self.assertEqual(
            normalize_phone_numbers(None, "", "None"),
            "",
        )

    def test_incomplete_number(self):
        self.assertEqual(
            normalize_phone_numbers("555-0101"),
            "",
        )

    def test_excess_digits(self):
        self.assertEqual(
            normalize_phone_numbers("123456789012"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
