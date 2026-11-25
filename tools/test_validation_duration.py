"""Regression for real JUnit grouping and diagnostic fields in saved device logs."""
import unittest
from collect_validation import instrumentation_seconds


class DeviceDurationTest(unittest.TestCase):
    def test_normal_footer(self):
        self.assertEqual(658.324, instrumentation_seconds("stream=\n\nTime: 658.324\n\nOK (199 tests)\n"))

    def test_actual_over_thousand_second_footer(self):
        self.assertEqual(1032.813, instrumentation_seconds("Time: 1,032.813\nThere were 2 failures:\n"))

    def test_earlier_diagnostic_time_does_not_replace_the_final_footer(self):
        self.assertEqual(1032.813, instrumentation_seconds("lastActivityTime: 1\nTime: 4.5\nmore diagnostics\nTime: 1,032.813\n"))

    def test_absent_or_malformed_footer_is_not_zero_or_a_partial_number(self):
        for text in ["No footer", "ActivityTime: 1", "Time: 1,,032.813", "Time: 1,03.813"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                instrumentation_seconds(text)


if __name__ == "__main__":
    unittest.main()
