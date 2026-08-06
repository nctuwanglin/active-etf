# -*- coding: utf-8 -*-
"""永豐投信(sitc.sinopac.com)adapter。

server-rendered HTML,且 ETF 代號直接是網址參數,不用查基金代碼對照。

資料源(2026-08-06 探勘):
- GET https://sitc.sinopac.com/SinopacEtfs/Etfs/SinglePcf/00410A
    「資料日期：2026/08/05」為持股基準日;
    持股表:<tr><td>2330</td><td>台積電</td><td>80,000</td><td>8.46</td></tr>
    (證券代碼/證券名稱/股數/佔基金淨資產之權重(%))

兩個要小心的地方:
1. 單檔頁面裡仍留著全系列 ETF 的「空表格模板」(共 36 個「證券代碼」表頭,
   只有第一個有資料),故只掃第一個表頭到第二個表頭之間。
   /Etfs/Pcf 那頁則是把 12 檔全部串在一起,不要拿來解析。
2. 「基金淨資產價值」在頁面上出現多次(其他基金的殘留區塊),取錯會拿到別檔的
   規模。這裡不賭位置,改用 units × nav 交叉驗證挑最接近的那個值。

受益人數不取:頁面把各基金的受益人數敘述(含已註解掉的舊區塊)混在同一段免責
文字裡,無法可靠對應到本檔,寧可留 None 也不要顯示別檔的數字。
"""
import html
import re

from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

SINGLE_PCF = "https://sitc.sinopac.com/SinopacEtfs/Etfs/SinglePcf/{}"

ROW_RE = re.compile(
    r"<tr>\s*<td>\s*([0-9A-Z]{4,6})\s*</td>\s*<td>\s*([^<]+?)\s*</td>\s*"
    r"<td>\s*([\d,]+)\s*</td>\s*<td>\s*([\d.]+)\s*</td>")
DATE_RE = re.compile(r"資料日期：\s*(\d{4}/\d{2}/\d{2})")


def _all_values(plain, label):
    return [to_num(v) for v in
            re.findall(re.escape(label) + r"\s*(?:NT\$)?\s*([\d,]+(?:\.\d+)?)", plain)]


def pick_scale(candidates, units, nav):
    """從多個「基金淨資產價值」候選值挑出與 units×nav 最相符的那個。

    頁面殘留其他基金的區塊,單純取第一個會在版面調整時默默拿到別檔規模。
    """
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    if not (units and nav):
        return candidates[0]
    expected = units * nav
    return min(candidates, key=lambda c: abs(c - expected))


def parse_single_pcf(page_html, etf_code):
    """SinglePcf 頁 → (data_date, [Holding], meta)"""
    t = html.unescape(page_html)
    m = DATE_RE.search(t)
    if not m:
        raise AdapterError("{}: 永豐頁面找不到「資料日期」(改版?)".format(etf_code))
    data_date = m.group(1).replace("/", "-")
    heads = [x.start() for x in re.finditer("證券代碼", t)]
    if not heads:
        raise AdapterError("{}: 永豐頁面找不到持股表(改版?)".format(etf_code))
    seg = t[heads[0]:heads[1]] if len(heads) > 1 else t[heads[0]:]
    holdings = [Holding(code=c, name=n, shares=int(s.replace(",", "")),
                        weight=float(w))
                for c, n, s, w in ROW_RE.findall(seg)]
    plain = re.sub(r"<[^>]+>", " ", t)
    units = (_all_values(plain, "已發行受益權單位總數") or [None])[0]
    nav = (_all_values(plain, "每受益權單位淨資產價值(元)") or [None])[0]
    meta = {"scale": pick_scale(_all_values(plain, "基金淨資產價值(元)"), units, nav),
            "units": units, "nav_per_unit": nav,
            "holders": None}  # 頁面無法可靠對應到本檔,見模組說明
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    code = etf["code"]
    return parse_single_pcf(get(SINGLE_PCF.format(code)).text, code)


ADAPTERS["sinopac"] = fetch_holdings
