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


class CarryStaleNoRegressionTests(unittest.TestCase):
    """同一資料日重跑、某檔抓失敗時,不可把先前那次抓到的較新持股蓋成更舊的。

    2026-08-08 實際事故:本機連不上野村,--force 重跑把 Actions 已寫入的
    08-06 持股蓋回前日快照的 08-05。
    """

    def _reg(self):
        return {"00980A": {"code": "00980A", "market": "tw", "status": "active"}}

    def test_prefers_newer_today_snapshot(self):
        import update_dashboard as ud
        prev = {"etfs": {"00980A": {"data_date": "2026-08-05", "status": "ok",
                                    "holdings": [{"code": "2330", "name": "台積電",
                                                  "shares": 100, "weight": 5.0}]}}}
        today = {"etfs": {"00980A": {"data_date": "2026-08-06", "status": "ok",
                                     "holdings": [{"code": "2330", "name": "台積電",
                                                   "shares": 200, "weight": 6.0}]}}}
        results = {}
        ud.carry_stale(results, self._reg(), prev, today)
        self.assertEqual(results["00980A"]["data_date"], "2026-08-06")
        self.assertEqual(results["00980A"]["holdings"][0].shares, 200)
        self.assertEqual(results["00980A"]["status"], "stale")

    def test_falls_back_to_prev_when_no_today(self):
        import update_dashboard as ud
        prev = {"etfs": {"00980A": {"data_date": "2026-08-05", "status": "ok",
                                    "holdings": [{"code": "2330", "name": "台積電",
                                                  "shares": 100, "weight": 5.0}]}}}
        results = {}
        ud.carry_stale(results, self._reg(), prev, None)
        self.assertEqual(results["00980A"]["data_date"], "2026-08-05")

    def test_successful_fetch_is_never_overwritten(self):
        import update_dashboard as ud
        prev = {"etfs": {"00980A": {"data_date": "2026-08-05", "status": "ok",
                                    "holdings": [{"code": "2330", "name": "台積電",
                                                  "shares": 100, "weight": 5.0}]}}}
        results = {"00980A": {"status": "ok", "data_date": "2026-08-07",
                              "holdings": [], "meta": {}}}
        ud.carry_stale(results, self._reg(), prev, None)
        self.assertEqual(results["00980A"]["status"], "ok")
        self.assertEqual(results["00980A"]["data_date"], "2026-08-07")


class SnapshotMetaPersistenceTests(unittest.TestCase):
    """B07:快照必須保存基本面,否則 stale 沿用時 NAV/規模/受益人數整組消失。

    carry_stale 讀 best.get("meta"),但 write_snapshot 從來沒寫過 meta——
    這個欄位永遠是 {}。既有 26 份快照全都沒有 meta,讀取端必須相容。
    """

    def _results(self):
        from adapters.base import Holding
        return {"00981A": {"status": "ok", "data_date": "2026-09-08",
                           "holdings": [Holding("2330", "台積電", 1000, 9.5)],
                           "events": [],
                           "meta": {"scale": 1000.0, "nav_per_unit": 10.0,
                                    "holders": 123, "nav_date": "2026-09-08"}}}

    def test_snapshot_round_trip_keeps_meta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            outputs.write_snapshot("2026-09-08", self._results(), tmp)
            snap = outputs.load_snapshot(tmp, "2026-09-08")
            m = snap["etfs"]["00981A"].get("meta") or {}
            self.assertEqual(m.get("nav_per_unit"), 10.0)
            self.assertEqual(m.get("holders"), 123)
            self.assertEqual(m.get("nav_date"), "2026-09-08")

    def test_carry_stale_preserves_fundamentals(self):
        import tempfile
        import update_dashboard as ud
        reg = {"00981A": {"code": "00981A", "market": "tw", "status": "active"}}
        with tempfile.TemporaryDirectory() as tmp:
            outputs.write_snapshot("2026-09-08", self._results(), tmp)
            prev = outputs.load_snapshot(tmp, "2026-09-08")
            carried = {}
            ud.carry_stale(carried, reg, prev, None)
            self.assertEqual(carried["00981A"]["status"], "stale")
            self.assertEqual(carried["00981A"]["meta"].get("nav_per_unit"), 10.0)

    def test_reads_legacy_snapshot_without_meta(self):
        """既有 26 份快照沒有 meta 欄位,不能因此炸掉。"""
        import update_dashboard as ud
        reg = {"00981A": {"code": "00981A", "market": "tw", "status": "active"}}
        legacy = {"etfs": {"00981A": {"status": "ok", "data_date": "2026-09-07",
                                      "holdings": [{"code": "2330", "name": "台積電",
                                                    "shares": 1, "weight": 5.0}]}}}
        carried = {}
        ud.carry_stale(carried, reg, legacy, None)
        self.assertEqual(carried["00981A"]["meta"], {})


class NoDateRegressionTests(unittest.TestCase):
    """B05:成功抓到「較舊」的資料時,不可覆蓋較新持股,也不可產生反向假事件。

    carry_stale 只保護「抓取失敗」;抓取成功但拿到舊快取會直接採用。
    compute_all_events 又只排除「日期相等」,於是 curr < prev 仍會算出事件——
    方向剛好相反(把買回讀成賣出)。
    """

    def _reg(self):
        return {"00981A": {"code": "00981A", "market": "tw", "status": "active"}}

    def _snap(self, date, shares):
        return {"etfs": {"00981A": {"status": "ok", "data_date": date,
                                    "holdings": [{"code": "2330", "name": "台積電",
                                                  "shares": shares, "weight": 9.5}]}}}

    def test_older_successful_fetch_is_rejected(self):
        import update_dashboard as ud
        from adapters.base import Holding
        results = {"00981A": {"status": "ok", "data_date": "2026-09-07",
                              "holdings": [Holding("2330", "台積電", 500, 5.0)],
                              "meta": {}}}
        ud.reject_regressions(results, self._snap("2026-09-08", 1000))
        r = results["00981A"]
        self.assertEqual(r["data_date"], "2026-09-08", "不可倒退回 09-07")
        self.assertEqual(r["holdings"][0].shares, 1000, "應保留較新的持股")
        self.assertEqual(r["status"], "stale")

    def test_newer_fetch_passes_through(self):
        import update_dashboard as ud
        from adapters.base import Holding
        results = {"00981A": {"status": "ok", "data_date": "2026-09-09",
                              "holdings": [Holding("2330", "台積電", 1200, 11.0)],
                              "meta": {}}}
        ud.reject_regressions(results, self._snap("2026-09-08", 1000))
        self.assertEqual(results["00981A"]["data_date"], "2026-09-09")
        self.assertEqual(results["00981A"]["status"], "ok")

    def test_events_only_when_date_advances(self):
        import update_dashboard as ud
        results = {"00981A": {"status": "ok", "data_date": "2026-09-07",
                              "holdings": [__import__("adapters.base", fromlist=["x"]).Holding(
                                  "2330", "台積電", 500, 5.0)], "meta": {}}}
        ud.compute_all_events(results, self._snap("2026-09-08", 1000))
        self.assertEqual(results["00981A"]["events"], [],
                         "日期倒退不可產生事件(會是方向相反的假事件)")


class PerEtfSkipGateTests(unittest.TestCase):
    """B01:跳過與否要逐檔判斷,不能只看全體資料日的眾數。

    原本 should_skip 只比全域眾數:第一輪寫入 09-08 後,18:00 補跑即使有 ETF
    從 stale 恢復、或單檔日期前進,只要眾數仍是 09-08 就整批 return——
    野村連續數日 stale 就是這樣卡住的。
    """

    def _res(self, pairs):
        from adapters.base import Holding
        return {c: {"status": "ok", "data_date": d,
                    "holdings": [Holding("2330", "台積電", n, 9.5)], "meta": {}}
                for c, d, n in pairs}

    def test_identical_rerun_skips(self):
        cur = self._res([("A", "2026-09-08", 100), ("B", "2026-09-08", 200)])
        state = outputs.results_fingerprint(cur)
        self.assertTrue(outputs.should_skip_results(cur, state))

    def test_single_etf_date_advance_does_not_skip(self):
        before = self._res([("A", "2026-09-08", 100), ("B", "2026-09-07", 200)])
        state = outputs.results_fingerprint(before)
        after = self._res([("A", "2026-09-08", 100), ("B", "2026-09-08", 250)])
        self.assertFalse(outputs.should_skip_results(after, state),
                         "單檔日期前進(眾數不變)也必須更新")

    def test_stale_recovery_does_not_skip(self):
        """野村情境:第一輪 stale,補跑成功抓到——眾數沒變但必須寫入。"""
        from adapters.base import Holding
        before = self._res([("A", "2026-09-08", 100)])
        before["N"] = {"status": "stale", "data_date": "2026-09-05",
                       "holdings": [Holding("2330", "台積電", 50, 5.0)], "meta": {}}
        state = outputs.results_fingerprint(before)
        after = self._res([("A", "2026-09-08", 100), ("N", "2026-09-08", 80)])
        self.assertFalse(outputs.should_skip_results(after, state))

    def test_holdings_change_same_date_does_not_skip(self):
        """同日官方更正內容:日期一樣但持股不同,不可跳過。"""
        before = self._res([("A", "2026-09-08", 100)])
        state = outputs.results_fingerprint(before)
        after = self._res([("A", "2026-09-08", 999)])
        self.assertFalse(outputs.should_skip_results(after, state))


class PremiumDateGuardTests(unittest.TestCase):
    """B03:折溢價只在「NAV 日 == 收盤價日」時才算。

    原本 quote_date 只被 log 出來就丟掉,舊 NAV 配最新收盤價仍會產生精確到
    小數兩位的折溢價。實例:00980A 持股日 09-07、NAV 25.18,配 09-08 的
    close 24.83 顯示 −1.39%——那不是同日折溢價,卻長得像。
    """

    def _r(self, data_date, nav):
        return {"00980A": {"status": "ok", "data_date": data_date, "holdings": [],
                           "meta": {"nav_per_unit": nav, "nav_date": data_date}}}

    def test_same_day_computes_premium(self):
        import update_dashboard as ud
        f = ud.build_fundamentals(self._r("2026-09-08", 25.0),
                                  {"00980A": 25.5}, "2026-09-08")
        self.assertAlmostEqual(f["00980A"]["premium_pct"], 2.0, places=2)
        self.assertIsNone(f["00980A"].get("premium_note"))

    def test_cross_day_refuses_premium(self):
        import update_dashboard as ud
        f = ud.build_fundamentals(self._r("2026-09-07", 25.18),
                                  {"00980A": 24.83}, "2026-09-08")
        self.assertIsNone(f["00980A"]["premium_pct"], "跨日不可輸出折溢價")
        self.assertIn("2026-09-07", f["00980A"]["premium_note"])
        self.assertIn("2026-09-08", f["00980A"]["premium_note"])
        self.assertEqual(f["00980A"]["close"], 24.83, "收盤價本身仍要保留")

    def test_nav_date_defaults_to_holdings_date(self):
        """adapter 未提供 nav_date 時,以持股基準日為準(PCF 同一份文件公告)。"""
        import update_dashboard as ud
        r = {"00980A": {"status": "ok", "data_date": "2026-09-08", "holdings": [],
                        "meta": {"nav_per_unit": 25.0}}}
        f = ud.build_fundamentals(r, {"00980A": 25.5}, "2026-09-08")
        self.assertEqual(f["00980A"]["nav_date"], "2026-09-08")
        self.assertAlmostEqual(f["00980A"]["premium_pct"], 2.0, places=2)


class QuoteFailureToleranceTests(unittest.TestCase):
    """報價來源掛掉不該讓整批更新化為烏有。

    2026-09-13 實際發生:持股 22 檔全部抓成功、事件也算完了(52 筆),
    但 TPEx 回 IncompleteRead → AdapterError 直接往上炸,流程在寫入前中止,
    快照與 active.json 全都停在舊版。持股才是主產品,報價只影響折溢價與估值。
    """

    def test_one_market_down_still_returns_other(self):
        import quotes
        calls = {}

        def fake_get(url, **kw):
            if "tpex" in url:
                raise quotes.AdapterError("TPEx 掛了")
            calls["twse"] = True
            raise AssertionError("不該走到這裡")  # 由下面的 monkeypatch 取代

        # 直接測合併邏輯:TWSE 有資料、TPEx 失敗
        date, merged, failed = quotes.merge_quotes(
            ("2026-09-11", {"2330": 100.0}), None, ["tpex"])
        self.assertEqual(date, "2026-09-11")
        self.assertEqual(merged["2330"], 100.0)
        self.assertEqual(failed, ["tpex"])

    def test_both_markets_down_returns_empty_not_raise(self):
        import quotes
        date, merged, failed = quotes.merge_quotes(None, None, ["twse", "tpex"])
        self.assertIsNone(date)
        self.assertEqual(merged, {})
        self.assertEqual(failed, ["twse", "tpex"])

    def test_twse_date_wins_when_both_present(self):
        import quotes
        date, merged, failed = quotes.merge_quotes(
            ("2026-09-11", {"2330": 100.0}), ("2026-09-10", {"6488": 50.0}), [])
        self.assertEqual(date, "2026-09-11")
        self.assertEqual(sorted(merged), ["2330", "6488"])


class PerfStatsUpsertTests(unittest.TestCase):
    """B06:同日重算要能撤回/更正事件,不能只追加。

    去重鍵是 (date, etf, code, type):誤判的事件更正後仍留著、close 修正無效、
    類型改變還會同時留下兩筆互相矛盾的事件。這關係到「加碼後表現回測」的資料品質。
    """

    def _res(self, events):
        return {"00981A": {"status": "ok", "data_date": "2026-09-08",
                           "holdings": [], "events": events}}

    def test_recompute_to_empty_removes_stale_event(self):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            f = _P(tmp) / "perf.json"
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "ADD"}]),
                                  {"2330": 100.0})
            outputs.append_events(f, "2026-09-08", self._res([]), {"2330": 100.0})
            evs = json.loads(f.read_text())["events"]
            self.assertEqual(evs, [], "更正為無事件時,舊事件必須消失")

    def test_type_change_does_not_keep_both(self):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            f = _P(tmp) / "perf.json"
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "ADD"}]), {})
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "INCREASE"}]), {})
            types = [e["type"] for e in json.loads(f.read_text())["events"]]
            self.assertEqual(types, ["INCREASE"], "不可同時留下 ADD 與 INCREASE")

    def test_close_correction_applies(self):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            f = _P(tmp) / "perf.json"
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "ADD"}]), {})
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "ADD"}]),
                                  {"2330": 123.0})
            self.assertEqual(json.loads(f.read_text())["events"][0]["close"], 123.0)

    def test_failed_etf_keeps_existing_events(self):
        """暫時抓取失敗不得刪掉既有有效事件。"""
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            f = _P(tmp) / "perf.json"
            outputs.append_events(f, "2026-09-08",
                                  self._res([{"code": "2330", "type": "ADD"}]), {})
            stale = {"00981A": {"status": "stale", "data_date": "2026-09-08",
                                "holdings": [], "events": []}}
            outputs.append_events(f, "2026-09-08", stale, {})
            self.assertEqual(len(json.loads(f.read_text())["events"]), 1)

    def test_other_dates_untouched(self):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            f = _P(tmp) / "perf.json"
            outputs.append_events(f, "2026-09-05",
                                  self._res([{"code": "1111", "type": "ADD"}]), {})
            outputs.append_events(f, "2026-09-08", self._res([]), {})
            dates = [e["date"] for e in json.loads(f.read_text())["events"]]
            self.assertEqual(dates, ["2026-09-05"], "其他日期的事件不可被動到")
