# -*- coding: utf-8 -*-
"""第一金投信 adapter 固定測資測試(fixture 為 2026-08-07 實抓的 00408A)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import firstsec
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "firstsec"


class FirstsecTests(unittest.TestCase):
    def setUp(self):
        self.hd = json.loads((FIX / "get_hd_00408A.json").read_text())
        self.bs = json.loads((FIX / "get_buysella_00408A.json").read_text())

    def test_parse_hd(self):
        data_date, holdings = firstsec.parse_hd(self.hd, "00408A")
        self.assertEqual(data_date, "2026-08-07")
        self.assertEqual(len(holdings), 40)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 45999)
        self.assertAlmostEqual(by["2330"].weight, 6.59, places=2)

    def test_only_stock_group_kept(self):
        """回應含 group 1/4/5,只有 1 是股票;混進其他組權重會爆掉。"""
        groups = {str(r.get("group")) for r in self.hd}
        self.assertTrue({"4", "5"} & groups, "fixture 應含非股票組才驗得到")
        _, holdings = firstsec.parse_hd(self.hd, "00408A")
        self.assertLess(sum(h.weight for h in holdings), 100.0)

    def test_sdate_is_basis_date(self):
        """第一金的 sdate 直接就是持股基準日,不用從公告日往回推。"""
        data_date, _ = firstsec.parse_hd(self.hd, "00408A")
        self.assertEqual(data_date, self.hd[0]["sdate"][:10])

    def test_parse_meta(self):
        meta = firstsec.parse_meta(self.bs)
        self.assertEqual(meta["units"], 163134000.0)
        self.assertGreater(meta["scale"], 1e9)
        self.assertIsNotNone(meta["nav_per_unit"])

    def test_empty_rows_raise(self):
        with self.assertRaises(AdapterError):
            firstsec.parse_hd([{"group": "4", "A": "現金", "B": "", "C": "1", "D": "1"}],
                              "00408A")

    def test_registered(self):
        self.assertIn("firstsec", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
