# -*- coding: utf-8 -*-
"""diff engine 測試:申贖等比例校正、四類事件、門檻邊界。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters.base import Holding
from diffengine import compute_events


def H(code, shares, weight, name="X"):
    return Holding(code=code, name=name, shares=shares, weight=weight)


def snap(*hs):
    return {h.code: h for h in hs}


class DiffTests(unittest.TestCase):
    def test_pure_creation_no_events(self):
        # 申購使全部股數 +10%,權重不變 → 無事件
        prev = snap(H("2330", 100000, 20.0), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        curr = snap(H("2330", 110000, 20.0), H("2317", 220000, 10.0),
                    H("2454", 55000, 5.0))
        self.assertEqual(compute_events(prev, curr), [])

    def test_increase_over_scale(self):
        # 規模效應 +10%,其中 2330 股數 +32%、權重 +2pp → INCREASE
        prev = snap(H("2330", 100000, 20.0), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        curr = snap(H("2330", 132000, 22.0), H("2317", 220000, 10.0),
                    H("2454", 55000, 5.0))
        evs = compute_events(prev, curr)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["type"], "INCREASE")
        self.assertEqual(evs[0]["code"], "2330")
        self.assertAlmostEqual(evs[0]["shares_delta_pct"], 20.0, delta=0.5)

    def test_add_and_remove(self):
        prev = snap(H("2330", 100000, 20.0), H("1101", 5000, 1.0))
        curr = snap(H("2330", 100000, 20.0), H("3661", 2000, 1.5))
        evs = {e["type"]: e for e in compute_events(prev, curr)}
        self.assertEqual(evs["ADD"]["code"], "3661")
        self.assertEqual(evs["REMOVE"]["code"], "1101")

    def test_threshold_boundary_no_event(self):
        # 校正後 +4.9%(門檻 5%)→ 無事件;三檔共同持股使中位數 scale=1
        prev = snap(H("2330", 100000, 20.0), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        curr = snap(H("2330", 104900, 20.5), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        self.assertEqual(compute_events(prev, curr), [])

    def test_weight_gate_blocks_noise(self):
        # 股數 +8% 但權重反而降(股價跌)→ 不算加碼
        prev = snap(H("2330", 100000, 20.0), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        curr = snap(H("2330", 108000, 19.5), H("2317", 200000, 10.0),
                    H("2454", 50000, 5.0))
        self.assertEqual(compute_events(prev, curr), [])


if __name__ == "__main__":
    unittest.main()


class TrueMedianTests(unittest.TestCase):
    """B09:偶數筆要取真中位數(中央兩值平均),不是右側中央值。

    上中位數會改變 scale,進而改變事件是否跨過 5% 門檻。
    """

    def test_even_count_uses_average_of_middle_two(self):
        # 比例 0.8/0.8/1.0/1.0 → 真中位數 0.9;上中位數會是 1.0
        prev = {c: Holding(c, c, 1000, 5.0) for c in ("A", "B", "C", "D")}
        curr = {"A": Holding("A", "A", 800, 5.0), "B": Holding("B", "B", 800, 5.0),
                "C": Holding("C", "C", 1000, 5.2), "D": Holding("D", "D", 1000, 5.0)}
        evs = {e["code"]: e["type"] for e in compute_events(prev, curr)}
        # scale=0.9 → C 校正後 +11.1%,權重 +0.2 → 應判定 INCREASE
        self.assertEqual(evs.get("C"), "INCREASE",
                         "真中位數 0.9 下 C 應達門檻;上中位數 1.0 會漏掉")

    def test_odd_count_unchanged(self):
        prev = {c: Holding(c, c, 1000, 5.0) for c in ("A", "B", "C")}
        curr = {"A": Holding("A", "A", 1000, 5.0), "B": Holding("B", "B", 1000, 5.0),
                "C": Holding("C", "C", 1200, 5.3)}
        evs = {e["code"]: e["type"] for e in compute_events(prev, curr)}
        self.assertEqual(evs.get("C"), "INCREASE")

    def test_empty_intersection_falls_back_to_one(self):
        prev = {"X": Holding("X", "X", 100, 5.0)}
        curr = {"Y": Holding("Y", "Y", 100, 5.0)}
        types = sorted(e["type"] for e in compute_events(prev, curr))
        self.assertEqual(types, ["ADD", "REMOVE"])


class AdjustedDeltaTests(unittest.TestCase):
    """B04:事件方向用「校正後」幅度,張數/金額卻用未校正的原始差額。

    大量申購時所有持股同步放大,原始差額含資金流;方向與數量可能不一致
    (同一筆 INCREASE 卻帶負張數)。兩個數字都要保留並各自命名清楚。
    """

    def test_keeps_both_raw_and_adjusted(self):
        # 3 檔共同持股 1000→900/800/800,scale=0.8;第一檔權重 +0.2
        prev = {c: Holding(c, c, 1000, 5.0) for c in ("A", "B", "C")}
        curr = {"A": Holding("A", "A", 900, 5.2), "B": Holding("B", "B", 800, 5.0),
                "C": Holding("C", "C", 800, 5.0)}
        ev = {e["code"]: e for e in compute_events(prev, curr)}["A"]
        self.assertEqual(ev["type"], "INCREASE", "校正後 +12.5% → 加碼")
        self.assertEqual(ev["shares_delta"], -100, "原始差額保留(含申購贖回影響)")
        self.assertEqual(ev["adjusted_shares_delta"], 100,
                         "校正後差額 = 900 - 1000*0.8 = +100,與方向一致")
        self.assertAlmostEqual(ev["scale"], 0.8, places=4)

    def test_scale_one_keeps_both_equal(self):
        prev = {c: Holding(c, c, 1000, 5.0) for c in ("A", "B", "C")}
        curr = {"A": Holding("A", "A", 1200, 5.3), "B": Holding("B", "B", 1000, 5.0),
                "C": Holding("C", "C", 1000, 5.0)}
        ev = {e["code"]: e for e in compute_events(prev, curr)}["A"]
        self.assertEqual(ev["shares_delta"], 200)
        self.assertEqual(ev["adjusted_shares_delta"], 200)
