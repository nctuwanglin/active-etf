# -*- coding: utf-8 -*-
"""adapters/base 驗證邏輯測試。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters.base import AdapterError, Holding, validate_holdings


def h(code, weight, shares=1000, name="測試"):
    return Holding(code=code, name=name, shares=shares, weight=weight)


class ValidateTests(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([], "00981A")

    def test_weight_sum_too_low_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([h("2330", 40.0), h("2317", 40.0)], "00981A")

    def test_weight_sum_with_cash_ok(self):
        out = validate_holdings([h("2330", 60.0), h("2317", 38.7)], "00981A")
        self.assertEqual(len(out), 2)

    def test_code_normalized(self):
        out = validate_holdings([h("2330 ", 60.0), h(" 2317", 38.7)], "00981A")
        self.assertEqual([x.code for x in out], ["2330", "2317"])

    def test_negative_shares_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([h("2330", 98.0, shares=-5)], "00981A")


if __name__ == "__main__":
    unittest.main()
