# -*- coding: utf-8 -*-
"""國泰投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓的 00400A)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import cathay
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "cathay"


def load(name):
    return json.loads((FIX / name).read_text())


class CathayTests(unittest.TestCase):
    def setUp(self):
        self.stocks = load("stocks_00400A.json")["result"]
        self.bs = load("buysale_00400A.json")["result"]
        self.weights = load("weights_00400A.json")["result"]["stockWeights"]
        self.baskets = (float(self.bs["totUnit"].replace(",", ""))
                        / float(self.bs["basketUnit"].replace(",", "")))

    def test_parse_fund_map(self):
        fm = cathay.parse_fund_map(load("etflist.json")["result"])
        self.assertEqual(fm["00400A"], "EA")

    def test_shares_reconstructed_from_basket(self):
        """國泰只公告「每基數股數」,總股數 = basketShares × 流通基數。"""
        h = cathay.build_holdings(self.stocks, self.weights, self.baskets, "00400A")
        by = {x.code: x for x in h}
        # 1303 南亞:每基數 145 股 × 4246.28 基數 ≈ 615,710 股
        self.assertAlmostEqual(by["1303"].shares, 145 * self.baskets, delta=1)
        self.assertGreater(by["2330"].shares, 1_000_000)

    def test_weights_are_official_not_derived(self):
        h = cathay.build_holdings(self.stocks, self.weights, self.baskets, "00400A")
        by = {x.code: x for x in h}
        wmap = {r["stockCode"]: float(r["weights"]) for r in self.weights}
        self.assertAlmostEqual(by["2330"].weight, wmap["2330"], places=4)

    def test_all_pcf_stocks_matched(self):
        """PCF 與權重表實測完全對齊;若某天不對齊,至少不能靜默少一半。"""
        h = cathay.build_holdings(self.stocks, self.weights, self.baskets, "00400A")
        self.assertEqual(len(h), len(self.stocks))

    def test_no_overlap_raises(self):
        with self.assertRaises(AdapterError):
            cathay.build_holdings(self.stocks, [{"stockCode": "9999",
                                                 "weights": "1.0"}],
                                  self.baskets, "00400A")

    def test_registered(self):
        self.assertIn("cathay", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
