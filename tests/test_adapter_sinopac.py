# -*- coding: utf-8 -*-
"""永豐投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓的 00410A)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import sinopac
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "sinopac"


class SinopacTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIX / "singlepcf_00410A.html").read_text()

    def test_parse_single_pcf(self):
        data_date, holdings, meta = sinopac.parse_single_pcf(self.page, "00410A")
        self.assertEqual(data_date, "2026-08-05")
        self.assertEqual(len(holdings), 35)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 80000)
        self.assertAlmostEqual(by["2330"].weight, 8.46, places=2)

    def test_only_first_table_scanned(self):
        """頁面留著全系列 ETF 的空表格模板,掃過頭會混入別檔或重複。"""
        _, holdings, _ = sinopac.parse_single_pcf(self.page, "00410A")
        codes = [h.code for h in holdings]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertLess(sum(h.weight for h in holdings), 105.0)

    def test_scale_picked_by_cross_check(self):
        """淨資產有多個候選(其他基金殘留),要挑與 units×nav 相符的那個。"""
        _, _, meta = sinopac.parse_single_pcf(self.page, "00410A")
        self.assertEqual(meta["scale"], 1963686481.0)
        self.assertAlmostEqual(meta["scale"], meta["units"] * meta["nav_per_unit"],
                               delta=meta["scale"] * 0.01)

    def test_pick_scale_prefers_consistent_value(self):
        self.assertEqual(
            sinopac.pick_scale([2272654975.0, 1963686481.0], 179860000.0, 10.92),
            1963686481.0)

    def test_pick_scale_falls_back_without_units(self):
        self.assertEqual(sinopac.pick_scale([123.0, 456.0], None, None), 123.0)
        self.assertIsNone(sinopac.pick_scale([], 1.0, 2.0))

    def test_missing_date_raises(self):
        with self.assertRaises(AdapterError):
            sinopac.parse_single_pcf("<html>證券代碼</html>", "00410A")

    def test_registered(self):
        self.assertIn("sinopac", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
