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


class HoldingValidationTests(unittest.TestCase):
    """優化 #6:權重合計正常不代表持股沒問題。

    重複代號在 diffengine 用 dict 會被覆蓋(少算),在反查卻會累加(多算),
    同一份資料兩邊結論不一致——這種錯最難查。
    """

    def test_duplicate_code_rejected(self):
        rows = [Holding("2330", "台積電", 100, 30.0),
                Holding("2330", "台積電", 200, 30.0)]
        with self.assertRaises(AdapterError) as cm:
            validate_holdings(rows, "00981A")
        self.assertIn("重複", str(cm.exception))

    def test_empty_code_rejected(self):
        rows = [Holding("", "現金", 100, 60.0)]
        with self.assertRaises(AdapterError):
            validate_holdings(rows, "00981A")

    def test_non_finite_weight_rejected(self):
        rows = [Holding("2330", "台積電", 100, float("nan"))]
        with self.assertRaises(AdapterError):
            validate_holdings(rows, "00981A")

    def test_single_weight_over_100_rejected(self):
        rows = [Holding("2330", "台積電", 100, 101.0)]
        with self.assertRaises(AdapterError):
            validate_holdings(rows, "00981A")

    def test_normal_holdings_still_pass(self):
        rows = [Holding("2330", "台積電", 100, 30.0),
                Holding("2454", "聯發科", 200, 25.0)]
        out = validate_holdings(rows, "00981A")
        self.assertEqual(len(out), 2)
