# -*- coding: utf-8 -*-
"""outputs 層測試:確定性、skip 判斷、驟降異常、事件庫去重、active.json 聚合。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import outputs
from adapters.base import Holding


def H(code, shares, weight, name="X"):
    return Holding(code=code, name=name, shares=shares, weight=weight)


def results():
    return {
        "00981A": {"status": "ok", "data_date": "2026-08-05",
                   "holdings": [H("2330", 100, 20.0, "台積電"),
                                H("2317", 200, 5.0, "鴻海")],
                   "events": [{"code": "2330", "name": "台積電",
                               "type": "INCREASE", "weight": 20.0,
                               "shares": 100, "prev_weight": 19.0,
                               "weight_delta": 1.0, "shares_delta_pct": 8.0}]},
        "00991A": {"status": "ok", "data_date": "2026-08-05",
                   "holdings": [H("2330", 50, 15.0, "台積電")],
                   "events": [{"code": "2330", "name": "台積電",
                               "type": "INCREASE", "weight": 15.0,
                               "shares": 50, "prev_weight": 14.5,
                               "weight_delta": 0.5, "shares_delta_pct": 6.0}]},
    }


class OutputsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_deterministic(self):
        p1 = outputs.write_snapshot("2026-08-05", results(), self.dir / "h")
        b1 = p1.read_bytes()
        p2 = outputs.write_snapshot("2026-08-05", results(), self.dir / "h")
        self.assertEqual(b1, p2.read_bytes())

    def test_load_prev_snapshot(self):
        outputs.write_snapshot("2026-08-04", results(), self.dir / "h")
        outputs.write_snapshot("2026-08-05", results(), self.dir / "h")
        prev = outputs.load_prev_snapshot(self.dir / "h", "2026-08-05")
        self.assertEqual(prev["date"], "2026-08-04")
        self.assertIsNone(outputs.load_prev_snapshot(self.dir / "h", "2026-08-04"))

    def test_should_skip(self):
        lc = self.dir / "last_counts.json"
        self.assertFalse(outputs.should_skip("2026-08-05", lc))
        outputs.update_last_counts("2026-08-05", {"00981A": 2}, lc)
        self.assertTrue(outputs.should_skip("2026-08-05", lc))
        self.assertTrue(outputs.should_skip("2026-08-04", lc))
        self.assertFalse(outputs.should_skip("2026-08-06", lc))

    def test_check_anomaly(self):
        lc = self.dir / "last_counts.json"
        outputs.update_last_counts("2026-08-04", {"00981A": 50}, lc)
        self.assertEqual(outputs.check_anomaly({"00981A": 20}, lc), ["00981A"])
        self.assertEqual(outputs.check_anomaly({"00981A": 48}, lc), [])

    def test_append_events_dedup(self):
        pp = self.dir / "perf_stats.json"
        outputs.append_events(pp, "2026-08-05", results(), {"2330": 1000.0})
        doc = outputs.append_events(pp, "2026-08-05", results(), {"2330": 1000.0})
        self.assertEqual(len(doc["events"]), 2)  # 兩檔 ETF 各一筆,重跑不重複
        self.assertEqual(doc["events"][0]["close"], 1000.0)

    def test_build_active_json(self):
        reg = {"00981A": {"name": "主動統一台股增長", "issuer": "統一",
                          "market": "tw", "status": "active"},
               "00991A": {"name": "主動復華未來50", "issuer": "復華",
                          "market": "tw", "status": "active"},
               "00988A": {"name": "主動統一全球創新", "issuer": "統一",
                          "market": "foreign", "status": "active"}}
        fundamentals = {"00981A": {"scale": 3.07e11, "nav_per_unit": 27.75,
                                   "holders": 1052004, "close": 27.63,
                                   "premium_pct": -0.42}}
        doc = outputs.build_active_json("2026-08-05", reg, results(), fundamentals)
        self.assertNotIn("00988A", doc["etfs"])  # 海外型排除
        # 基本面 key 對映(meta 用 nav_per_unit,對外欄位名 nav)
        self.assertEqual(doc["etfs"]["00981A"]["nav"], 27.75)
        self.assertEqual(doc["etfs"]["00981A"]["holders"], 1052004)
        s = doc["stocks"]["2330"]
        self.assertAlmostEqual(s["total_weight"], 35.0)
        self.assertEqual(len(s["etfs"]), 2)
        # 兩檔同步加碼 → 共識榜
        self.assertEqual(doc["consensus"]["increase"][0]["code"], "2330")
        self.assertEqual(len(doc["consensus"]["increase"][0]["etfs"]), 2)
        self.assertEqual(doc["consensus"]["decrease"], [])


if __name__ == "__main__":
    unittest.main()


class ReverseIndexAggregateTests(unittest.TestCase):
    """反查索引的規模指標:total_value(股數×收盤價)才有量綱意義。"""

    def _build(self):
        reg = {"00981A": {"name": "A", "issuer": "統一", "market": "tw"},
               "00991A": {"name": "B", "issuer": "復華", "market": "tw"}}
        results = {
            "00981A": {"status": "ok", "data_date": "2026-08-05", "events": [],
                       "holdings": [Holding("2330", "台積電", 1000, 9.5)]},
            "00991A": {"status": "ok", "data_date": "2026-08-05", "events": [],
                       "holdings": [Holding("2330", "台積電", 500, 14.6)]},
        }
        return outputs.build_active_json("2026-08-05", reg, results, {},
                                         quotes={"2330": 1200.0})

    def test_total_shares_and_value(self):
        s = self._build()["stocks"]["2330"]
        self.assertEqual(s["total_shares"], 1500)
        self.assertEqual(s["total_value"], 1800000)
        self.assertEqual(s["etf_count"], 2)

    def test_total_value_none_without_quote(self):
        reg = {"00981A": {"name": "A", "issuer": "統一", "market": "tw"}}
        results = {"00981A": {"status": "ok", "data_date": "2026-08-05", "events": [],
                              "holdings": [Holding("9999", "無報價", 100, 1.0)]}}
        s = outputs.build_active_json("2026-08-05", reg, results, {}, quotes={})["stocks"]["9999"]
        self.assertIsNone(s["total_value"])
