import unittest

from core import validators


class ValidatorTests(unittest.TestCase):
    def test_full_name_accepts_polish_letters_hyphen_and_apostrophe(self):
        self.assertTrue(validators.is_valid_full_name("Anna-Maria O'Neil")[0])
        self.assertTrue(validators.is_valid_full_name("Łukasz Żółć")[0])

    def test_full_name_rejects_single_word_and_digits(self):
        self.assertFalse(validators.is_valid_full_name("Kowalski")[0])
        self.assertFalse(validators.is_valid_full_name("Jan Kowalski2")[0])

    def test_album_number_boundaries(self):
        self.assertTrue(validators.is_valid_album("1234")[0])
        self.assertTrue(validators.is_valid_album("123456")[0])
        self.assertFalse(validators.is_valid_album("123")[0])
        self.assertFalse(validators.is_valid_album("12A45")[0])

    def test_nip_checksum(self):
        self.assertTrue(validators.validate_nip("526-025-09-95")[0])
        self.assertFalse(validators.validate_nip("526-025-09-96")[0])
        self.assertTrue(validators.validate_nip("", required=False)[0])
        self.assertFalse(validators.validate_nip("", required=True)[0])

    def test_company_address_requires_name_and_building_number(self):
        self.assertTrue(validators.is_valid_address(
            "ul. Portowa 12, Elbląg", required=True,
        )[0])
        self.assertFalse(validators.is_valid_address(
            "ulica Portowa, Elbląg", required=True,
        )[0])

    def test_company_email_and_required_hours(self):
        self.assertTrue(validators.validate_email(
            "kontakt@firma.pl", required=True,
        )[0])
        self.assertFalse(validators.validate_email(
            "kontakt@firma", required=True,
        )[0])
        self.assertTrue(validators.validate_required_hours("960")[0])
        self.assertFalse(validators.validate_required_hours("240")[0])

    def test_dates_and_ranges(self):
        self.assertTrue(validators.is_valid_date("2026-06-06", required=True)[0])
        self.assertFalse(validators.is_valid_date("2026-02-30")[0])
        self.assertTrue(validators.validate_date_range(
            "2026-06-01", "2026-06-30",
        )[0])
        self.assertFalse(validators.validate_date_range(
            "2026-06-30", "2026-06-01",
        )[0])

    def test_diary_description_minimum_length(self):
        self.assertFalse(validators.validate_diary_opis("a" * 99)[0])
        self.assertTrue(validators.validate_diary_opis("a" * 100)[0])

    def test_diary_day_and_hours_limits(self):
        self.assertTrue(validators.validate_diary_day("1")[0])
        self.assertTrue(validators.validate_diary_day("120")[0])
        self.assertFalse(validators.validate_diary_day("121")[0])
        self.assertTrue(validators.validate_diary_hours("8")[0])
        self.assertFalse(validators.validate_diary_hours("0")[0])
        self.assertFalse(validators.validate_diary_hours("9")[0])


if __name__ == "__main__":
    unittest.main()
