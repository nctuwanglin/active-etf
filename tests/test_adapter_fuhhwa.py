# -*- coding: utf-8 -*-
"""復華投信 adapter 固定測資測試(fixture 為 2026-08-05 實抓)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import fuhhwa
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "fuhhwa"


class FuhhwaTests(unittest.TestCase):
    def test_parse_assets(self):
        d = json.loads((FIX / "assets_00991A.json").read_text())
        data_date, holdings, meta = fuhhwa.parse_assets(d, "00991A")
        self.assertGreater(meta["scale"], 1e9)
        self.assertGreater(meta["nav_per_unit"], 0)
        self.assertEqual(data_date, "2026-08-05")
        self.assertGreater(len(holdings), 40)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertAlmostEqual(by_code["2330"].weight, 14.638, places=3)
        self.assertEqual(by_code["2330"].shares, 5400000)
        # 其他資產(現金/應付款)不得混入
        self.assertNotIn("", by_code)

    def test_empty_returns_none(self):
        d = {"result": [{"dDate": None, "detail": []}]}
        data_date, holdings, meta = fuhhwa.parse_assets(d, "00991A")
        self.assertIsNone(holdings)

    def test_registered(self):
        self.assertIn("fuhhwa", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
