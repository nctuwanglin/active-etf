# -*- coding: utf-8 -*-
"""凱基投信(kgifund.com.tw)adapter。

目前為最單純的一家:純 server-rendered HTML,不需 session、token 或 API 探勘。

資料源(2026-08-06 探勘):
- GET https://www.kgifund.com.tw/Fund/RedemptionList
    下拉選單 <option value="J024">主動凱基台灣</option>,即 基金簡稱 ↔ fundID。
    簡稱與 TWSE 上市名稱一致(「主動凱基台灣」),故用 registry 的 name 對照,
    不硬編 fundID(將來新增主動式 ETF 會自動對上)。
- GET https://www.kgifund.com.tw/Fund/Detail?fundID=J024
    「持股比重 (YYYY/MM/DD)」為資料日;其後為基金資產與持股表:
      <tr name="content"><td>2330</td><td>台積電</td><td>991,000</td><td>7.98</td></tr>
    中文為 &#x..; 十六進位實體,需先 html.unescape。

兩個踩過的坑:
1. 頁面有「兩份」完全相同的持股表(桌機/行動各一),只取第一個表頭之後的區段,
   否則每檔持股會重複計算一次。
2. 部分列的代號帶尾端空白(如 '6669 '),cell 內容一律要吃掉前後空白,
   否則會靜默漏掉近半數持股(權重合計檢查會擋下,但別讓它走到那步)。

資料日語意:凱基標示的日期比各家 PCF 的資料日新一天(同一份持股,凱基標公告日、
PCF 標基準日)。各檔 ETF 的異動是各自與自己的前一份快照比對,故不影響其他家。
"""
import html
import re

from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

REDEMPTION = "https://www.kgifund.com.tw/Fund/RedemptionList"
DETAIL = "https://www.kgifund.com.tw/Fund/Detail"

ROW_RE = re.compile(
    r'<tr name="content"[^>]*>\s*<td[^>]*>\s*([0-9A-Z]{4,6})\s*</td>\s*'
    r'<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>\s*'
    r'<td[^>]*>\s*([\d.]+)\s*</td>')
# 標題與日期之間夾著標籤:持股比重</div> <p class="fund-asset__date">(2026/08/06)</p>
DATE_RE = re.compile(r"持股比重(?:<[^>]*>|\s)*\((\d{4}/\d{2}/\d{2})\)")
OPTION_RE = re.compile(r'<option[^>]*value="([A-Z0-9]+)"[^>]*>([^<]+)</option>')

_fund_map = None


def parse_fund_map(page_html):
    """RedemptionList 下拉 → {'主動凱基台灣': 'J024', …}"""
    t = html.unescape(page_html)
    return {name.strip(): fid for fid, name in OPTION_RE.findall(t) if name.strip()}


def _meta_value(plain, label):
    m = re.search(re.escape(label) + r"\s*(?:TWD\$)?\s*([\d,]+(?:\.\d+)?)", plain)
    return to_num(m.group(1)) if m else None


def parse_detail(page_html, etf_code):
    """Detail 頁 → (data_date, [Holding], meta)"""
    t = html.unescape(page_html)
    m = DATE_RE.search(t)
    if not m:
        raise AdapterError("{}: 凱基頁面找不到「持股比重 (日期)」(改版?)".format(etf_code))
    data_date = m.group(1).replace("/", "-")
    # 桌機/行動兩份相同的表,只取第一份
    first = t.find("股票代號")
    second = t.find("股票代號", first + 1)
    seg = t[first:second] if second > 0 else t[first:]
    holdings = [Holding(code=c, name=n, shares=int(s.replace(",", "")),
                        weight=float(w))
                for c, n, s, w in ROW_RE.findall(seg)]
    plain = re.sub(r"<[^>]+>", " ", t)
    meta = {"scale": _meta_value(plain, "基金淨值資產價值"),
            "units": _meta_value(plain, "基金在外流通單位數"),
            "nav_per_unit": _meta_value(plain, "基金每單位淨值"),
            "holders": None}  # 凱基頁面不揭露受益人數
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    global _fund_map
    code, name = etf["code"], (etf.get("name") or "").strip()
    if _fund_map is None:
        _fund_map = parse_fund_map(get(REDEMPTION).text)
    fund_id = _fund_map.get(name)
    if not fund_id:
        raise AdapterError("kgi: {} 名稱「{}」不在基金下拉清單".format(code, name))
    return parse_detail(get(DETAIL, params={"fundID": fund_id}).text, code)


ADAPTERS["kgi"] = fetch_holdings
