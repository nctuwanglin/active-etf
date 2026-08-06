# -*- coding: utf-8 -*-
"""群益投信 adapter 固定測資測試(fixture 為 2026-08-05 實抓)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import capital
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "capital"


class CapitalTests(unittest.TestCase):
    def test_parse_buyback(self):
        d = json.loads((FIX / "buyback_00982A.json").read_text())
        data_date, holdings, meta = capital.parse_buyback(d, "00982A")
        self.assertGreater(meta["scale"], 1e9)
        self.assertGreater(meta["holders"], 1000)
        self.assertEqual(data_date, "2026-08-05")
        self.assertEqual(len(holdings), 55)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertEqual(by_code["2330"].shares, 1794000)
        self.assertAlmostEqual(by_code["2330"].weight, 8.522, places=3)

    def test_fund_map(self):
        items = json.loads((FIX / "items.json").read_text())
        fm = capital.parse_fund_map(items)
        self.assertEqual(fm["00982A"], "399")
        self.assertEqual(fm["00992A"], "500")

    def test_registered(self):
        self.assertIn("capital", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
