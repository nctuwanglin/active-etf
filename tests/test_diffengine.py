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
