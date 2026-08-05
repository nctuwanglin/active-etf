# -*- coding: utf-8 -*-
"""統一投信(ezmoney.com.tw)adapter。

資料源(2026-08-05 探勘):
- GET  https://www.ezmoney.com.tw/ETF/Transaction/PCF
    建立 session cookie;頁面內 <div id="DataFundList" data-content="…">
    為 html-escaped JSON,含 sStockNo(股票代號)↔ sFundCode(內部基金代碼)對照。
- POST https://www.ezmoney.com.tw/ETF/Transaction/GetPCF
    body JSON {fundCode, date(民國 '115/08/05'), specificDate}
    date 給未來日 + specificDate=false → 回最新一份 PCF。
    specificDate=true + 過去營業日 → 可查歷史(回填選項,本 adapter 未用)。
- 回應 asset[] 中 AssetCode=='ST' 之 Details 為持股(DetailCode/DetailName/
  Share/NavRate);pcf[0].TranDate 為持股資料日(兩種 .NET 日期格式都可能出現)。
"""
import datetime
import html
import json
import re

from .base import (ADAPTERS, AdapterError, Holding, get, post,
                   parse_dotnet_date, roc_date, validate_holdings)

PCF_PAGE = "https://www.ezmoney.com.tw/ETF/Transaction/PCF"
GETPCF = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"

_fund_map = None


def parse_fund_map(page_html):
    """從 PCF 頁抽 DataFundList 對照:{'00981A': '49YTW', …}"""
    m = re.search(r"id=['\"]DataFundList['\"][^>]*data-content=['\"](.*?)['\"]",
                  page_html, re.S)
    if not m:
        raise AdapterError("president: PCF 頁找不到 DataFundList(改版?)")
    funds = json.loads(html.unescape(m.group(1)))
    return {(f.get("sStockNo") or "").strip(): f["sFundCode"]
            for f in funds if f.get("sStockNo")}


def parse_pcf(d, etf_code):
    """GetPCF 回應 → (data_date, [Holding])"""
    stock_assets = [a for a in d.get("asset", []) if a.get("AssetCode") == "ST"]
    if not stock_assets or not stock_assets[0].get("Details"):
        raise AdapterError("{}: GetPCF 無股票明細".format(etf_code))
    holdings = [Holding(code=str(r["DetailCode"]), name=str(r["DetailName"]),
                        shares=int(r["Share"]), weight=float(r["NavRate"]))
                for r in stock_assets[0]["Details"]]
    pcf = d.get("pcf") or []
    if not pcf:
        raise AdapterError("{}: GetPCF 無 pcf 摘要(資料日不明)".format(etf_code))
    data_date = parse_dotnet_date(pcf[0]["TranDate"])
    return data_date, validate_holdings(holdings, etf_code)


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    if _fund_map is None:
        _fund_map = parse_fund_map(get(PCF_PAGE).text)  # 同時建立 session cookie
    if code not in _fund_map:
        raise AdapterError("president: {} 不在 fundList".format(code))
    query_date = roc_date(datetime.date.today() + datetime.timedelta(days=3))
    r = post(GETPCF, json={"fundCode": _fund_map[code], "date": query_date,
                           "specificDate": False},
             headers={"Referer": PCF_PAGE})
    try:
        d = r.json()
    except ValueError:
        raise AdapterError("president: {} GetPCF 回非 JSON(session/改版?)".format(code))
    return parse_pcf(d, code)


ADAPTERS["president"] = fetch_holdings
