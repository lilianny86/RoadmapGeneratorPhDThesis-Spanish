from __future__ import annotations

import unittest

from display_format import format_clp, format_decimal, format_integer, format_percentage


class DisplayFormatTests(unittest.TestCase):
    def test_decimal_values_use_a_comma_and_two_places(self) -> None:
        self.assertEqual(format_decimal(1), "1,00")
        self.assertEqual(format_decimal(3.456), "3,46")

    def test_discrete_values_do_not_show_decimal_places(self) -> None:
        self.assertEqual(format_integer(21), "21")
        self.assertEqual(format_integer(2.0), "2")
        self.assertEqual(format_integer(1000), "1.000")

    def test_percentages_use_a_comma_and_two_places(self) -> None:
        self.assertEqual(format_percentage(50), "50,00%")

    def test_clp_values_use_periods_for_thousands_and_a_decimal_comma(self) -> None:
        self.assertEqual(format_clp(1000000, "Not available"), "CLP $ 1.000.000,00")
        self.assertEqual(format_clp(1250.5, "Not available"), "CLP $ 1.250,50")

    def test_missing_clp_value_uses_the_localized_placeholder(self) -> None:
        self.assertEqual(format_clp(None, "No estimable"), "No estimable")


if __name__ == "__main__":
    unittest.main()
