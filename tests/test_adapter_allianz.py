# -*- coding: utf-8 -*-
"""安聯投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓,持股資料日 08-05)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import allianz
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "allianz"


class AllianzTests(unittest.TestCase):
    def test_parse_tradeinfo(self):
        d = json.loads((FIX / "tradeinfo_00993A.json").read_text())
        data_date, holdings, meta = allianz.parse_tradeinfo(d, "00993A")
        self.assertEqual(data_date, "2026-08-05")
        self.assertEqual(len(holdings), 49)
        by_code = {h.code: h for h in holdings}
        self.assertEqual(by_code["2330"].shares, 518000)
        self.assertAlmostEqual(by_code["2330"].weight, 12.54, places=2)

    def test_parses_formatted_strings(self):
        """DynamicTableData 的股數帶千分位、權重帶 %,都是字串。"""
        d = json.loads((FIX / "tradeinfo_00993A.json").read_text())
        _, holdings, _ = allianz.parse_tradeinfo(d, "00993A")
        by_code = {h.code: h for h in holdings}
        self.assertEqual(by_code["2344"].shares, 1235000)   # '1,235,000'
        self.assertAlmostEqual(by_code["2344"].weight, 2.11, places=2)  # '2.11%'

    def test_meta(self):
        d = json.loads((FIX / "tradeinfo_00993A.json").read_text())
        _, _, meta = allianz.parse_tradeinfo(d, "00993A")
        self.assertEqual(meta["scale"], 9910844518.0)
        self.assertEqual(meta["holders"], 51811)
        self.assertAlmostEqual(meta["nav_per_unit"], 12.86, places=2)

    def test_parse_fund_map(self):
        d = json.loads((FIX / "fundlist.json").read_text())
        fm = allianz.parse_fund_map(d)
        self.assertEqual(fm["00993A"], "E0002")
        self.assertEqual(fm["00984A"], "E0001")
        self.assertNotIn("", fm)  # 佔位列「查無基金」不得混入

    def test_pick_active_type_id(self):
        self.assertEqual(allianz.pick_active_type_id(
            {"Entries": [{"Name": "指數股票型基金", "Id": 2},
                         {"Name": "主動式交易所交易基金", "Id": 6}]}), 6)

    def test_pick_active_type_id_raises_when_missing(self):
        with self.assertRaises(AdapterError):
            allianz.pick_active_type_id({"Entries": [{"Name": "債券型", "Id": 9}]})

    def test_empty_entries_returns_none(self):
        self.assertIsNone(allianz.parse_tradeinfo({"Entries": None}, "00993A")[1])

    def test_registered(self):
        self.assertIn("allianz", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
