# -*- coding: utf-8 -*-
"""富邦投信(websys.fsit.com.tw)adapter。

資料源(2026-08-05 探勘):
- GET https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId=00405A&lan=TW
    server-rendered 基金資產頁;不帶 ddate 參數即回最新資料。
    持股表列格式:
      <tr><td class="tac">2330</td><td>台積電</td>
          <td class="tar">179,000</td><td class="tar">430,495,000</td>
          <td class="tar">1.4173</td></tr>
    (代號/名稱/股數/市值/權重%)。現金列為兩欄結構、代號欄為中文,不會誤抓。
- 資料日:頁面「資料日期：2026/08/05」。
- 基本面另在 Pcf.aspx?stkId=…&lan=TW,版型為 <p>標題</p><p>值</p> 配對。
"""
import re

from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

ASSETS_URL = "https://websys.fsit.com.tw/FubonETF/Trade/Assets.aspx"
PCF_URL = "https://websys.fsit.com.tw/FubonETF/Trade/Pcf.aspx"

ROW_RE = re.compile(
    r'<tr>\s*<td class="tac">([0-9A-Z]{4,6})</td>\s*<td>([^<]+)</td>'
    r'\s*<td class="tar">([\d,]+)</td>\s*<td class="tar">[\d,.-]+</td>'
    r'\s*<td class="tar">([\d.]+)</td>')
DATE_RE = re.compile(r"資料日期：(\d{4}/\d{2}/\d{2})")


def parse_assets(page_html, etf_code):
    m = DATE_RE.search(page_html)
    if not m:
        raise AdapterError("{}: 富邦資產頁找不到資料日期(改版?)".format(etf_code))
    data_date = m.group(1).replace("/", "-")
    holdings = [Holding(code=c, name=n, shares=int(s.replace(",", "")),
                        weight=float(w))
                for c, n, s, w in ROW_RE.findall(page_html)]
    return data_date, validate_holdings(holdings, etf_code)


def _pcf_value(page_html, label):
    m = re.search(re.escape(label) + r"[^<]*</p>\s*<p>([^<]+)</p>", page_html)
    return to_num(m.group(1)) if m else None


def parse_pcf_meta(page_html):
    return {"scale": _pcf_value(page_html, "基金淨資產價值"),
            "units": _pcf_value(page_html, "已發行受益權單位總數"),
            "nav_per_unit": _pcf_value(page_html, "每受益權單位淨資產價值"),
            "holders": _pcf_value(page_html, "受益人人數")}


def fetch_holdings(etf):
    code = etf["code"]
    r = get(ASSETS_URL, params={"stkId": code, "lan": "TW"})
    data_date, holdings = parse_assets(r.text, code)
    try:
        meta = parse_pcf_meta(get(PCF_URL, params={"stkId": code, "lan": "TW"}).text)
    except AdapterError:
        meta = None  # 基本面抓不到不影響持股主資料
    return data_date, holdings, meta


ADAPTERS["fubon"] = fetch_holdings
