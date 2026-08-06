# -*- coding: utf-8 -*-
"""單檔 ETF 抓取失敗時沿用前日快照的行為。

2026-08-06 中信投信網域 DNS SERVFAIL(連 8.8.8.8 都解不出),兩檔 ETF 整批抓不到——
這條路徑是真的會走到的,不是理論上的防呆。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import update_dashboard as ud


REG = {
    "00981A": {"code": "00981A", "market": "tw", "status": "active", "name": "A"},
    "00406A": {"code": "00406A", "market": "tw", "status": "active", "name": "B"},
    "00983A": {"code": "00983A", "market": "foreign", "status": "active", "name": "海外"},
}
PREV = {"date": "2026-08-04", "etfs": {
    "00406A": {"status": "ok", "data_date": "2026-08-04",
               "holdings": [{"code": "2330", "name": "台積電",
                             "shares": 610000, "weight": 9.1}]},
    "00983A": {"status": "ok", "data_date": "2026-08-04",
               "holdings": [{"code": "TSLA US", "name": "TESLA",
                             "shares": 100, "weight": 5.0}]},
}}


class CarryStaleTests(unittest.TestCase):
    def test_failed_etf_carries_prev_holdings_as_stale(self):
        results = {"00981A": {"status": "ok", "data_date": "2026-08-05",
                              "holdings": [], "meta": {}}}
        ud.carry_stale(results, REG, PREV)
        self.assertIn("00406A", results)
        self.assertEqual(results["00406A"]["status"], "stale")
        self.assertEqual(results["00406A"]["data_date"], "2026-08-04")
        self.assertEqual(results["00406A"]["holdings"][0].code, "2330")

    def test_successful_etf_is_not_overwritten(self):
        results = {"00406A": {"status": "ok", "data_date": "2026-08-05",
                              "holdings": [], "meta": {}}}
        ud.carry_stale(results, REG, PREV)
        self.assertEqual(results["00406A"]["status"], "ok")
        self.assertEqual(results["00406A"]["data_date"], "2026-08-05")

    def test_stale_etf_produces_no_events(self):
        """沿用的持股與前日相同,若拿去比對會產生一堆假異動,故 events 必須為空。"""
        results = {}
        ud.carry_stale(results, REG, PREV)
        ud.compute_all_events(results, PREV)
        self.assertEqual(results["00406A"]["events"], [])

    def test_no_prev_snapshot_is_safe(self):
        results = {}
        ud.carry_stale(results, REG, None)
        self.assertEqual(results, {})

    def test_foreign_etf_not_carried(self):
        results = {}
        ud.carry_stale(results, REG, PREV)
        self.assertNotIn("00983A", results)


if __name__ == "__main__":
    unittest.main()
