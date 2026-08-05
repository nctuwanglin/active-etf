# -*- coding: utf-8 -*-
"""中信投信 adapter 固定測資測試(fixture 為 2026-08-05 實抓)。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import ctbc
from adapters.base import ADAPTERS

FIX = Path(__file__).parent / "fixtures" / "ctbc"


class CtbcTests(unittest.TestCase):
    def test_parse_holding(self):
        d = json.loads((FIX / "holding_00406A.json").read_text())
        data_date, holdings = ctbc.parse_holding(d, "00406A")
        self.assertEqual(data_date, "2026-08-05")
        self.assertEqual(len(holdings), 56)
        by_code = {h.code: h for h in holdings}
        self.assertIn("2330", by_code)
        self.assertEqual(by_code["2330"].shares, 610000)
        self.assertAlmostEqual(by_code["2330"].weight, 9.10, places=2)

    def test_parse_etflist(self):
        d = json.loads((FIX / "etflist.json").read_text())
        fm = ctbc.parse_etflist(d)
        self.assertEqual(fm["00406A"], "E0038")
        self.assertEqual(fm["00995A"], "E0036")

    def test_resultcode_fail_returns_none(self):
        data_date, holdings = ctbc.parse_holding({"ResultCode": 1}, "00406A")
        self.assertIsNone(holdings)

    def test_registered(self):
        self.assertIn("ctbc", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
