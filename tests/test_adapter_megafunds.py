# -*- coding: utf-8 -*-
"""兆豐投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓的 00996A)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import megafunds
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "megafunds"


class MegafundsTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIX / "result_00996A.html").read_text()

    def test_parse_result(self):
        data_date, holdings, meta = megafunds.parse_result(self.page, "00996A")
        self.assertEqual(data_date, "2026-08-06")
        self.assertEqual(len(holdings), 50)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 179000)
        self.assertAlmostEqual(by["2330"].weight, 9.71, places=2)

    def test_data_date_is_basis_not_effective(self):
        """頁面「查詢日期」是公告生效日(T+1),持股基準日是其後那個(T)。"""
        data_date, _, _ = megafunds.parse_result(self.page, "00996A")
        self.assertIn("查詢日期", self.page.replace("\n", ""))
        self.assertEqual(data_date, "2026-08-06")  # 而非查詢日期 2026/08/07

    def test_meta(self):
        _, _, meta = megafunds.parse_result(self.page, "00996A")
        self.assertEqual(meta["scale"], 4359425644.0)
        self.assertEqual(meta["units"], 322399000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 13.52, places=2)

    def test_wrong_fund_page_raises(self):
        """對照錯基金時結果頁不會有該代號,要當場報錯而不是回別檔的持股。"""
        with self.assertRaises(AdapterError):
            megafunds.parse_result(self.page, "00408A")

    def test_fund_map_and_pick(self):
        fm = megafunds.parse_fund_map((FIX / "fundlist.html").read_text())
        self.assertEqual(fm["兆豐台灣豐收主動式ETF基金"], "23")
        # registry 名稱去「主動」前綴後,是下拉選項的前綴
        self.assertEqual(megafunds.pick_fund_id(fm, "主動兆豐台灣豐收"), "23")
        self.assertIsNone(megafunds.pick_fund_id(fm, "主動兆豐不存在"))

    def test_registered(self):
        self.assertIn("megafunds", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
