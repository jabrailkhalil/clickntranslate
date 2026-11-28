"""Regression for real JUnit grouping and diagnostic fields in saved device logs."""
import unittest
from collect_validation import instrumentation_seconds


class DeviceDurationTest(unittest.TestCase):
    def test_normal_footer(self):
        self.assertEqual(658.324, instrumentation_seconds("stream=\n\nTime: 658.324\n\nOK (199 tests)\n"))

    def test_actual_over_thousand_second_footer(self):
        self.assertEqual(1032.813, instrumentation_seconds("Time: 1,032.813\nThere were 2 failures:\n"))

    def test_localized_decimal_and_group_separators(self):
        for value, expected in [('3,908', 3.908), ('12,5', 12.5), ('1.032,813', 1032.813),
                                ('1\u202f032,813', 1032.813), ('١٬٠٣٢٫٨١٣', 1032.813)]:
            with self.subTest(value=value):
                self.assertEqual(expected, instrumentation_seconds(f"Time: {value}\n"))

    def test_recorded_wall_time_disambiguates_a_whole_thousand_seconds(self):
        for value in ('1,032', '1.032'):
            with self.subTest(value=value):
                self.assertEqual(1032, instrumentation_seconds(f"Time: {value}\nQA_WALL_SECONDS=1035\n"))
                self.assertEqual(1.032, instrumentation_seconds(f"Time: {value}\nQA_WALL_SECONDS=5\n"))

    def test_earlier_diagnostic_time_does_not_replace_the_final_footer(self):
        self.assertEqual(1032.813, instrumentation_seconds("lastActivityTime: 1\nTime: 4.5\nmore diagnostics\nTime: 1,032.813\n"))

    def test_absent_or_malformed_footer_is_not_zero_or_a_partial_number(self):
        for text in ["No footer", "ActivityTime: 1", "Time: 1,,032.813", "Time: 1,03.813"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                instrumentation_seconds(text)


if __name__ == "__main__":
    unittest.main()
