# -*- coding: utf-8 -*-
"""台新投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓的 00987A)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import taishin
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "taishin"


class TaishinTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIX / "detail_00987A.html").read_text()

    def test_parse_detail(self):
        data_date, holdings, meta = taishin.parse_detail(self.page, "00987A")
        self.assertEqual(data_date, "2026-08-06")
        self.assertEqual(len(holdings), 27)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 90000)
        self.assertAlmostEqual(by["2330"].weight, 8.0505, places=4)

    def test_taiwan_ticker_suffix_stripped(self):
        """台新用 '2330 TT' 這種 Bloomberg ticker,不還原會與其他家對不起來。"""
        self.assertEqual(taishin.normalize_code("2330 TT"), "2330")
        self.assertEqual(taishin.normalize_code(" 6669 TT "), "6669")

    def test_foreign_ticker_suffix_kept(self):
        """海外持股保留後綴——剝掉會讓不同市場代號混淆,也會被誤算成台股權重。"""
        self.assertEqual(taishin.normalize_code("MU US"), "MU US")
        self.assertEqual(taishin.normalize_code("7203 JP"), "7203 JP")

    def test_meta(self):
        _, _, meta = taishin.parse_detail(self.page, "00987A")
        self.assertEqual(meta["scale"], 2688646214.0)
        self.assertEqual(meta["units"], 177143000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 15.18, places=2)

    def test_missing_date_raises(self):
        with self.assertRaises(AdapterError):
            taishin.parse_detail("<html>沒有 PUB_DATE</html>", "00987A")

    def test_registered(self):
        self.assertIn("taishin", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
