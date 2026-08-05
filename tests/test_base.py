# -*- coding: utf-8 -*-
"""adapters/base 驗證邏輯測試。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters.base import (AdapterError, Holding, parse_dotnet_date,
                           validate_holdings)


def h(code, weight, shares=1000, name="測試"):
    return Holding(code=code, name=name, shares=shares, weight=weight)


class ValidateTests(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([], "00981A")

    def test_weight_sum_too_low_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([h("2330", 20.0), h("2317", 15.0)], "00981A")

    def test_weight_sum_with_cash_futures_ok(self):
        # 實測主動式 ETF 股票部位可低至 84%(其餘現金/期貨)
        out = validate_holdings([h("2330", 60.0), h("2317", 24.0)], "00981A")
        self.assertEqual(len(out), 2)

    def test_code_normalized(self):
        out = validate_holdings([h("2330 ", 60.0), h(" 2317", 38.7)], "00981A")
        self.assertEqual([x.code for x in out], ["2330", "2317"])

    def test_negative_shares_raises(self):
        with self.assertRaises(AdapterError):
            validate_holdings([h("2330", 98.0, shares=-5)], "00981A")


class DotnetDateTests(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_dotnet_date("2026-08-04T00:00:00"), "2026-08-04")

    def test_ms_epoch_taipei_midnight(self):
        # 1785772800000 = 2026-08-04 00:00 台北(UTC 解會錯成 08-03)
        self.assertEqual(parse_dotnet_date("/Date(1785772800000)/"), "2026-08-04")


if __name__ == "__main__":
    unittest.main()
