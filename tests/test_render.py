# -*- coding: utf-8 -*-
"""render_html 結構斷言(非像素):AUTO:DATE、三分頁、資料內嵌、無外部依賴。"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_html

ACTIVE = {
    "updated": "2026-08-05",
    "etfs": {
        "00981A": {"name": "主動統一台股增長", "issuer": "統一", "status": "ok",
                   "data_date": "2026-08-05", "scale": 3.07e11, "holders": 1052004,
                   "nav": 27.75, "close": 27.63, "premium_pct": -0.42,
                   "holdings": [{"code": "2330", "name": "台積電",
                                 "shares": 100, "weight": 20.0}],
                   "events": [{"code": "2330", "name": "台積電", "type": "INCREASE",
                               "weight": 20.0, "shares": 100, "prev_weight": 19.0,
                               "weight_delta": 1.0, "shares_delta_pct": 8.0}]},
        "00999A": {"name": "主動野村臺灣高息", "issuer": "野村", "status": "unsupported",
                   "data_date": None, "scale": None, "holders": None, "nav": None,
                   "close": None, "premium_pct": None, "holdings": [], "events": []},
    },
    "stocks": {"2330": {"name": "台積電", "total_weight": 20.0,
                        "etfs": [{"etf": "00981A", "weight": 20.0, "shares": 100}],
                        "recent_events": [{"etf": "00981A", "type": "INCREASE",
                                           "date": "2026-08-05"}]}},
    "consensus": {"increase": [], "decrease": []},
    "crosslinks": {"dispo": ["2330"], "notes": {}},
}


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.html = render_html.render(ACTIVE, {})

    def test_auto_date_marker_and_title(self):
        self.assertIn("<!-- AUTO:DATE:2026-08-05 -->", self.html)
        self.assertIn("<title>台股主動式ETF追蹤 | Updated 2026-08-05</title>", self.html)

    def test_three_tabs(self):
        for label in ("今日異動", "各檔 ETF", "個股反查"):
            self.assertIn(label, self.html)
        self.assertEqual(self.html.count("<section"), 3)

    def test_data_embedded(self):
        self.assertIn("const DATA = {", self.html)
        self.assertIn("主動統一台股增長", self.html)

    def test_self_contained(self):
        # 不得有任何外部資源(CSP/離線可用)
        self.assertEqual(re.findall(r'<(?:script|link)[^>]+(?:src|href)="http', self.html), [])

    def test_kpi_counts_only_tracked(self):
        # 追蹤 ETF 數只算有持股者(00999A unsupported 不計)
        self.assertRegex(self.html, r'<div class="n">1</div><div class="l">追蹤 ETF</div>')


if __name__ == "__main__":
    unittest.main()
