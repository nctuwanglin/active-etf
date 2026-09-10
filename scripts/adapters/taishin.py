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
# 頁面同時有兩個日期,語意不同,務必取 NAV_DATE:
#   PUB_DATE = 2026-09-11  公告生效日(T+1)
#   NAV_DATE = 2026/9/10   淨值/持股基準日(T)  ← 我們要的
# 2026-09-10 實抓證據見 test_uses_nav_date_not_pub_date。原本誤取 PUB_DATE,
# 使 00987A 的資料日比其他投信多一天,共識榜把不同持股日的 ETF 併成「今日」。
# (凱基已查證非同類問題:其「持股比重 (日期)」== LatestNAVDate,勿一併更動。)
NAV_DATE_RE = re.compile(r'id="NAV_DATE"[^>]*value="([^"]+)"')


def parse_nav_date(raw):
    """'2026/9/10 上午 12:00:00' → '2026-09-10';無法解析回 None。

    月日未補零、後面還跟著中文時間,故不能用固定寬度比對。
    """
    m = re.match(r"\s*(\d{4})/(\d{1,2})/(\d{1,2})", raw or "")
    if not m:
        return None
    y, mo, d = m.groups()
    return "{}-{:02d}-{:02d}".format(y, int(mo), int(d))


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
    m = NAV_DATE_RE.search(t)
    data_date = parse_nav_date(m.group(1)) if m else None
    if not data_date:
        raise AdapterError("{}: 台新頁面找不到可解析的 NAV_DATE(改版?)".format(etf_code))
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
