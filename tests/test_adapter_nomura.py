# -*- coding: utf-8 -*-
"""野村投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓,持股資料日 08-05)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import nomura
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "nomura"


class NomuraTests(unittest.TestCase):
    def test_parse_tradeinfo(self):
        d = json.loads((FIX / "tradeinfo_00980A.json").read_text())
        data_date, holdings, meta = nomura.parse_tradeinfo(d, "00980A")
        self.assertEqual(len(holdings), 50)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertEqual(by_code["2330"].shares, 663000)
        self.assertAlmostEqual(by_code["2330"].weight, 8.46, places=2)

    def test_data_date_uses_nav_date_not_announce_date(self):
        """CPcfdate 是公告日(T+1),資料日必須取 CNavDtStr,否則會與他家差一天。"""
        d = json.loads((FIX / "tradeinfo_00980A.json").read_text())
        self.assertTrue(d["Entries"]["CPcfdate"].startswith("2026-08-06"))
        data_date, _, _ = nomura.parse_tradeinfo(d, "00980A")
        self.assertEqual(data_date, "2026-08-05")

    def test_meta(self):
        d = json.loads((FIX / "tradeinfo_00980A.json").read_text())
        _, _, meta = nomura.parse_tradeinfo(d, "00980A")
        self.assertEqual(meta["scale"], 18848138780.0)
        self.assertEqual(meta["units"], 807230000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 23.35, places=2)
        self.assertEqual(meta["holders"], 72224)

    def test_empty_entries_returns_none(self):
        """假日/未來日回 Entries=null,須回 None 讓 fetch 往前一天重試。"""
        data_date, holdings, meta = nomura.parse_tradeinfo(
            {"StatusCode": 0, "Entries": None}, "00980A")
        self.assertIsNone(holdings)

    def test_registered(self):
        self.assertIn("nomura", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
