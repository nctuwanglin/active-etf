# -*- coding: utf-8 -*-
"""富邦投信 adapter 固定測資測試(fixture 為 2026-08-05 實抓)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import fubon
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "fubon"


class FubonTests(unittest.TestCase):
    def test_parse_assets(self):
        html_text = (FIX / "assets_00405A.html").read_text()
        data_date, holdings = fubon.parse_assets(html_text, "00405A")
        self.assertEqual(data_date, "2026-08-05")
        self.assertEqual(len(holdings), 49)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertEqual(by_code["2330"].shares, 179000)
        self.assertAlmostEqual(by_code["2330"].weight, 1.4173, places=4)
        total = sum(h.weight for h in holdings)
        self.assertTrue(50 <= total <= 105, total)

    def test_registered(self):
        self.assertIn("fubon", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
