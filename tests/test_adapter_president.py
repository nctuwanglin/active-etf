# -*- coding: utf-8 -*-
"""統一投信 adapter 固定測資測試(fixture 為 2026-08-05 實抓)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import president
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "president"


class PresidentTests(unittest.TestCase):
    def test_parse_holdings(self):
        d = json.loads((FIX / "getpcf_00981A.json").read_text())
        data_date, holdings, meta = president.parse_pcf(d, "00981A")
        self.assertGreater(meta["scale"], 1e9)
        self.assertGreater(meta["holders"], 1000)
        self.assertGreater(meta["nav_per_unit"], 0)
        self.assertEqual(data_date, "2026-08-04")
        self.assertEqual(len(holdings), 51)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertGreater(by_code["2330"].weight, 5)
        self.assertGreater(by_code["2330"].shares, 1000000)
        total = sum(h.weight for h in holdings)
        self.assertTrue(50 <= total <= 105, total)

    def test_fund_map_from_fragment(self):
        html_text = (FIX / "fundlist_fragment.html").read_text()
        fm = president.parse_fund_map(html_text)
        self.assertEqual(fm["00981A"], "49YTW")
        self.assertEqual(fm["00403A"], "63YTW")

    def test_registered(self):
        self.assertIn("president", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
