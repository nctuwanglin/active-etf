# -*- coding: utf-8 -*-
"""摩根投信 adapter 固定測資測試(fixture 為 2026-08-07 實抓的 00401A xlsx)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import jpmorgan
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "jpmorgan"


class JpmorganTests(unittest.TestCase):
    def setUp(self):
        self.holding = jpmorgan.read_xlsx((FIX / "holding_pcf_00401A.xlsx").read_bytes())
        self.m12 = jpmorgan.read_xlsx((FIX / "m12_pcf_00401A.xlsx").read_bytes())

    def test_read_xlsx_without_openpyxl(self):
        """本專案不裝 openpyxl,xlsx 直接以 zip+XML 解。"""
        self.assertTrue(self.holding)
        first = next(iter(self.holding.values()))
        self.assertIn("基金資產", first[0][0])

    def test_parse_holdings(self):
        data_date, holdings = jpmorgan.parse_holdings_xlsx(self.holding, "00401A")
        self.assertEqual(data_date, "2026-08-07")
        self.assertEqual(len(holdings), 63)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 178000)
        self.assertAlmostEqual(by["2330"].weight, 14.10, places=2)

    def test_only_stock_sheet(self):
        """檔案另有期貨/選擇權/現金三張表,混入權重會失真。"""
        _, holdings = jpmorgan.parse_holdings_xlsx(self.holding, "00401A")
        codes = {h.code for h in holdings}
        self.assertNotIn("FTQ6", codes)  # 期貨商品代碼
        self.assertLess(sum(h.weight for h in holdings), 100.0)

    def test_percent_sign_stripped(self):
        """權重欄是 '14.10%' 字串,不去掉 % 會整批解析失敗。"""
        _, holdings = jpmorgan.parse_holdings_xlsx(self.holding, "00401A")
        self.assertTrue(all(isinstance(h.weight, float) for h in holdings))

    def test_parse_meta(self):
        meta = jpmorgan.parse_meta_xlsx(self.m12)
        self.assertEqual(meta["scale"], 2992413651.0)
        self.assertEqual(meta["units"], 226395000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 13.22, places=2)

    def test_non_xlsx_raises(self):
        """參數不全時端點回 500 HTML,要當場報錯而不是當成空持股。"""
        with self.assertRaises(AdapterError):
            jpmorgan.read_xlsx(b"<html>500 error</html>")

    def test_registered(self):
        self.assertIn("jpmorgan", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
