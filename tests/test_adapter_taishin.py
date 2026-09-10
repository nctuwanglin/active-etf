# -*- coding: utf-8 -*-
"""台新投信 adapter 固定測資測試(fixture 為 2026-08-06 實抓的 00987A)。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adapters import taishin
from adapters.base import ADAPTERS, AdapterError

FIX = Path(__file__).parent / "fixtures" / "taishin"


class TaishinTests(unittest.TestCase):
    def setUp(self):
        self.page = (FIX / "detail_00987A.html").read_text()

    def test_parse_detail(self):
        data_date, holdings, meta = taishin.parse_detail(self.page, "00987A")
        self.assertEqual(data_date, "2026-09-10")
        self.assertEqual(len(holdings), 28)
        by = {h.code: h for h in holdings}
        self.assertEqual(by["2330"].shares, 90000)
        self.assertAlmostEqual(by["2330"].weight, 8.6654, places=4)

    def test_taiwan_ticker_suffix_stripped(self):
        """台新用 '2330 TT' 這種 Bloomberg ticker,不還原會與其他家對不起來。"""
        self.assertEqual(taishin.normalize_code("2330 TT"), "2330")
        self.assertEqual(taishin.normalize_code(" 2330 TT "), "2330")

    def test_foreign_ticker_suffix_kept(self):
        """海外持股保留後綴——剝掉會讓不同市場代號混淆,也會被誤算成台股權重。"""
        self.assertEqual(taishin.normalize_code("MU US"), "MU US")
        self.assertEqual(taishin.normalize_code("7203 JP"), "7203 JP")

    def test_meta(self):
        _, _, meta = taishin.parse_detail(self.page, "00987A")
        self.assertEqual(meta["scale"], 2544608539.0)
        self.assertEqual(meta["units"], 153143000.0)
        self.assertAlmostEqual(meta["nav_per_unit"], 16.62, places=2)

    def test_uses_nav_date_not_pub_date(self):
        """台新頁面同時有兩個日期,必須取 NAV_DATE(持股基準日 T)。

        2026-09-10 實抓證據:PUB_DATE=2026-09-11(公告生效日 T+1)、
        NAV_DATE=2026-09-10。原本讀 PUB_DATE 會讓 00987A 的資料日比其他
        投信整整多一天,共識榜因此把不同持股日的 ETF 混在一起算「今日」。
        (凱基已查證非同類問題:其「持股比重」日期 == LatestNAVDate。)
        """
        self.assertIn('id="PUB_DATE"', self.page)   # 誘餌欄位確實存在
        self.assertIn('id="NAV_DATE"', self.page)
        data_date, _, _ = taishin.parse_detail(self.page, "00987A")
        self.assertEqual(data_date, "2026-09-10")
        self.assertNotEqual(data_date, "2026-09-11")

    def test_nav_date_month_day_not_zero_padded(self):
        """NAV_DATE 是 '2026/9/10 上午 12:00:00' —— 月日未補零且帶中文時間,
        用固定寬度的 \d{2} 會整個比對不到。"""
        self.assertEqual(taishin.parse_nav_date("2026/9/10 上午 12:00:00"), "2026-09-10")
        self.assertEqual(taishin.parse_nav_date("2026/12/1 下午 03:00:00"), "2026-12-01")
        self.assertIsNone(taishin.parse_nav_date("(空)"))

    def test_missing_date_raises(self):
        with self.assertRaises(AdapterError):
            taishin.parse_detail("<html>沒有 PUB_DATE</html>", "00987A")

    def test_registered(self):
        self.assertIn("taishin", ADAPTERS)


if __name__ == "__main__":
    unittest.main()
