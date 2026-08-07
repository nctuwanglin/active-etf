# -*- coding: utf-8 -*-
"""聯博投信 adapter 固定測資測試(fixture 為 2026-08-07 實抓的 00404A)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import ab
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "ab"


class AbTests(unittest.TestCase):
    def setUp(self):
        self.holdings = json.loads((FIX / "holdings_00404A.json").read_text())
        self.basket = json.loads((FIX / "basket_00404A.json").read_text())

    def test_isin_check_digit(self):
        """ISIN 直接由代號算,不用查表;用兩個已知值鎖住算法。"""
        self.assertEqual(ab.isin_for("00404A"), "TW00000404A5")
        self.assertEqual(ab.isin_for("00980D"), "TW00000980D8")
        self.assertEqual(ab.isin_for("00401A"), "TW00000401A1")

    def test_parse_holdings(self):
        data_date, holdings = ab.parse_holdings(self.holdings, "00404A")
        self.assertEqual(data_date, "2026-08-06")
        self.assertEqual(len(holdings), 53)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 324000)

    def test_only_equity_section(self):
        """回應含 futures(權重 16%)與 options 分段,混進去權重合計會爆掉。"""
        cats = {s.get("holdingCategory") for s in self.holdings["domesticHoldings"]}
        self.assertIn("holdings-section-futures", cats)
        _, holdings = ab.parse_holdings(self.holdings, "00404A")
        self.assertLess(sum(h.weight for h in holdings), 100.0)

    def test_parse_basket(self):
        meta = ab.parse_basket(self.basket)
        self.assertEqual(meta["scale"], 3502239667.0)
        self.assertEqual(meta["units"], 368795000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 9.5, places=2)

    def test_bad_date_format_raises(self):
        bad = {"domesticHoldings": [{"holdingCategory": "holdings-section-equity",
                                     "asOfDate": "2026-08-06",
                                     "holdings": [{"holdingCode": "2330", "holding": "台積電",
                                                   "holdingShares": 1, "holdingPerc": "1"}]}]}
        with self.assertRaises(AdapterError):
            ab.parse_holdings(bad, "00404A")

    def test_registered(self):
        self.assertIn("ab", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
