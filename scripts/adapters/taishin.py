# -*- coding: utf-8 -*-
"""台新投信(tsit.com.tw)adapter。

server-rendered HTML,且 ETF 代號直接就是網址參數,連基金代碼對照都不用查。

資料源(2026-08-06 探勘):
- GET https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/00987A
    <input id="PUB_DATE" value="2026-08-06"> 為公告日;
    基金資產區塊有「基金淨資產價值(元) TWD 2,688,646,214」等欄位;
    持股表:<tr><td>2330 TT</td><td>台積電</td><td>90,000</td><td>8.0505%</td></tr>

代號格式:台新用 Bloomberg 式 ticker(「2330 TT」)。只剝掉台股的 " TT" 後綴還原成
「2330」,海外持股(如「MU US」)的後綴保留——剝掉會讓不同市場的同名代號混在一起,
而且保留後綴剛好讓 registry 的「台股權重」判定正確把它算成非台股。

頁面上另有一張期貨表(表頭「口數」),欄位結構與股票表(表頭「股數」)不同,
故只掃「股數」表頭之後的區段,避免期貨部位被當成持股。
"""
import html
import re

from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

DETAIL = "https://www.tsit.com.tw/ETF/Home/ETFSeriesDetail/{}"

ROW_RE = re.compile(
    r"<tr>\s*<td>\s*([0-9A-Z]{1,8}(?:\s+[A-Z]{2})?)\s*</td>\s*<td>\s*([^<]+?)\s*</td>"
    r"\s*<td>\s*([\d,]+)\s*</td>\s*<td>\s*([\d.]+)%\s*</td>")
DATE_RE = re.compile(r'id="PUB_DATE"[^>]*value="(\d{4}-\d{2}-\d{2})"')


def normalize_code(raw):
    """'2330 TT' → '2330';'MU US' 等非台股後綴保留原樣。"""
    raw = raw.strip()
    return raw[:-3].strip() if raw.endswith(" TT") else raw


def _meta_value(plain, label):
    m = re.search(re.escape(label) + r"\s*(?:TWD)?\s*([\d,]+(?:\.\d+)?)", plain)
    return to_num(m.group(1)) if m else None


def parse_detail(page_html, etf_code):
    """ETFSeriesDetail 頁 → (data_date, [Holding], meta)"""
    t = html.unescape(page_html)
    m = DATE_RE.search(t)
    if not m:
        raise AdapterError("{}: 台新頁面找不到 PUB_DATE(改版?)".format(etf_code))
    data_date = m.group(1)
    i = t.find("股數")  # 股票表表頭;其前為期貨表
    seg = t[i:] if i >= 0 else t
    holdings = [Holding(code=normalize_code(c), name=n,
                        shares=int(s.replace(",", "")), weight=float(w))
                for c, n, s, w in ROW_RE.findall(seg)]
    plain = re.sub(r"<[^>]+>", " ", t)
    meta = {"scale": _meta_value(plain, "基金淨資產價值(元)"),
            "units": _meta_value(plain, "已發行受益權單位總數"),
            "nav_per_unit": _meta_value(plain, "每受益權單位淨資產價值(元)"),
            "holders": None}  # 台新頁面不揭露受益人數
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    code = etf["code"]
    return parse_detail(get(DETAIL.format(code)).text, code)


ADAPTERS["taishin"] = fetch_holdings
