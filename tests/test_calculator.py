"""Behavioral tests for arithmetic rules, invalid input and input limits."""

import random
import unittest

from src.calculator import CalculationError, calculate_expression


class CalculatorTests(unittest.TestCase):
    def test_required_arithmetic(self):
        cases = {
            "12+8": "20",
            "8-3": "5",
            "6*7": "42",
            "9/4": "2.25",
            "1+2*3": "7",
            "(1+2)*3": "9",
            "10/2+7": "12",
            "8-3*2": "2",
            "-5+8": "3",
            "3*-2": "-6",
            "3*+2": "6",
            "-(1+2)*3": "-9",
            "+(-2+5)": "3",
            "0.1+0.2": "0.3",
            "1.20+2.30": "3.5",
            ".5+1.": "1.5",
            "  (2 + 3) × 4 ÷ 2  ": "10",
            "−5+8": "3",
            "1--2": "3",
            "--2": "2",
            "1+-2": "-1",
            "2*(3+(4/2))": "10",
            "0": "0",
            "-0.000": "0",
            "10*10": "100",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculate_expression(expression), expected)

    def test_equal_priority_is_left_associative(self):
        self.assertEqual(calculate_expression("8/2*2"), "8")
        self.assertEqual(calculate_expression("10-3-2"), "5")
        self.assertEqual(calculate_expression("20/2/5"), "2")

    def test_invalid_expressions_are_rejected(self):
        cases = [
            "1+", "*2", "1//2", "2**3", "()", "(1+2", "1+2)",
            "2(3+4)", "1 2", "1.2.3", ".", "1e3", "NaN", "Infinity",
            "abc", "1,2", "1;2", "[1]", "__import__('os')", "2%1",
            "（1+2）", "１２+3",
        ]
        for expression in cases:
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate_expression(expression)

    def test_empty_input_is_rejected(self):
        for expression in ("", "   ", "\n\t"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as caught:
                    calculate_expression(expression)
                self.assertEqual(caught.exception.code, "EMPTY_EXPRESSION")

    def test_expression_must_be_text(self):
        for expression in (None, 123, True, ["1+2"], {"value": "1+2"}):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as caught:
                    calculate_expression(expression)
                self.assertEqual(caught.exception.code, "INVALID_INPUT")

    def test_zero_divisors_are_rejected(self):
        for expression in ("1/0", "0/0", "1/(-0)", "5/(3-3)"):
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError) as caught:
                    calculate_expression(expression)
                self.assertEqual(caught.exception.code, "DIVISION_BY_ZERO")

    def test_expression_length_boundary(self):
        self.assertEqual(calculate_expression("+" * 499 + "1"), "1")
        with self.assertRaises(CalculationError) as caught:
            calculate_expression("+" * 500 + "1")
        self.assertEqual(caught.exception.code, "EXPRESSION_TOO_LONG")

    def test_nesting_boundary(self):
        self.assertEqual(calculate_expression("(" * 50 + "1" + ")" * 50), "1")
        with self.assertRaises(CalculationError) as caught:
            calculate_expression("(" * 51 + "1" + ")" * 51)
        self.assertEqual(caught.exception.code, "EXPRESSION_TOO_DEEP")

    def test_repeating_decimal_precision(self):
        self.assertEqual(
            calculate_expression("1/3"), "0.3333333333333333333333333333"
        )

    def test_large_and_small_numbers_are_not_binary_floats(self):
        self.assertEqual(
            calculate_expression("9007199254740992+1"), "9007199254740993"
        )
        self.assertEqual(
            calculate_expression("0.00000000000000000001/10"),
            "0.000000000000000000001",
        )

    def test_error_position_is_one_based(self):
        with self.assertRaises(CalculationError) as caught:
            calculate_expression("1 + a")
        self.assertEqual(caught.exception.position, 5)

    def test_integer_expressions_against_independent_arithmetic(self):
        generator = random.Random(42)
        for _ in range(100):
            a, b, c = [generator.randint(-100, 100) for _ in range(3)]
            expression = f"({a}+{b})*{c}-{a}"
            with self.subTest(expression=expression):
                self.assertEqual(
                    calculate_expression(expression), str((a + b) * c - a)
                )


if __name__ == "__main__":
    unittest.main()
