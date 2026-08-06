# -*- coding: utf-8 -*-
"""凱基投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import kgi
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "kgi"


class KgiTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIX / "detail_00407A.html").read_text()

    def test_parse_detail(self):
        data_date, holdings, meta = kgi.parse_detail(self.page, "00407A")
        self.assertEqual(data_date, "2026-08-06")
        self.assertEqual(len(holdings), 50)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 991000)
        self.assertAlmostEqual(by["2330"].weight, 7.98, places=2)

    def test_duplicate_tables_not_double_counted(self):
        """頁面有桌機/行動兩份相同持股表,重複計算會讓每檔出現兩次。"""
        _, holdings, _ = kgi.parse_detail(self.page, "00407A")
        codes = [h.code for h in holdings]
        self.assertEqual(len(codes), len(set(codes)))

    def test_code_cell_with_trailing_space(self):
        """部分列代號帶尾端空白(如 '6669 '),不吃掉會漏近半數持股。"""
        _, holdings, _ = kgi.parse_detail(self.page, "00407A")
        by = {h.code: h for h in holdings}
        self.assertIn("6669", by)
        self.assertEqual(by["6669"].shares, 205000)

    def test_meta(self):
        _, _, meta = kgi.parse_detail(self.page, "00407A")
        self.assertEqual(meta["scale"], 29371017299.0)
        self.assertEqual(meta["units"], 3098239000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 9.48, places=2)
        self.assertIsNone(meta["holders"])

    def test_parse_fund_map(self):
        fm = kgi.parse_fund_map((FIX / "redemption_options.html").read_text())
        self.assertEqual(fm["主動凱基台灣"], "J024")

    def test_registered(self):
        self.assertIn("kgi", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
