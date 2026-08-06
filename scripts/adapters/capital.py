# -*- coding: utf-8 -*-
"""群益投信(capitalfund.com.tw)adapter。

資料源(2026-08-05 探勘):
- POST https://www.capitalfund.com.tw/CFWeb/api/etf/items  body {}
    ETF 清單:data[] {fundNo, stockNo, shortName}(00982A ↔ 399)。
- POST https://www.capitalfund.com.tw/CFWeb/api/etf/buyback  body {"fundId":"399"}
    data.pcf.date2 = 持股資料日(date1 為次一營業日公告日);
    data.stocks[] {stocNo, stocName, weight, share}。
    站點有 Incapsula,但帶一般 UA 的 JSON POST 可直接通(2026-08-05 實測)。
"""
from .base import (ADAPTERS, AdapterError, Holding, post, to_num,
                   validate_holdings)

ITEMS = "https://www.capitalfund.com.tw/CFWeb/api/etf/items"
BUYBACK = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"

_fund_map = None


def parse_fund_map(items_json):
    return {(f.get("stockNo") or "").strip(): f["fundNo"]
            for f in items_json.get("data", []) if f.get("stockNo")}


def parse_buyback(d, etf_code):
    """buyback 回應 → (data_date, [Holding], meta)"""
    data = d.get("data") or {}
    stocks = data.get("stocks") or []
    pcf = data.get("pcf") or {}
    if not stocks or not pcf.get("date2"):
        raise AdapterError("{}: buyback 無持股/資料日".format(etf_code))
    holdings = [Holding(code=str(x["stocNo"]), name=str(x["stocName"]).strip(),
                        shares=int(x["share"]), weight=float(x["weight"]))
                for x in stocks]
    meta = {"scale": to_num(pcf.get("nav")), "units": to_num(pcf.get("totUnit")),
            "nav_per_unit": to_num(pcf.get("pUnit")),
            "holders": to_num(pcf.get("numberPeople"))}
    return pcf["date2"], validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    if _fund_map is None:
        r = post(ITEMS, json={}, headers={"Content-Type": "application/json"})
        try:
            _fund_map = parse_fund_map(r.json())
        except ValueError:
            raise AdapterError("capital: items 回非 JSON(Incapsula 擋?)")
    if code not in _fund_map:
        raise AdapterError("capital: {} 不在 items".format(code))
    r = post(BUYBACK, json={"fundId": _fund_map[code]},
             headers={"Content-Type": "application/json"})
    try:
        d = r.json()
    except ValueError:
        raise AdapterError("capital: {} buyback 回非 JSON(Incapsula 擋?)".format(code))
    return parse_buyback(d, code)


ADAPTERS["capital"] = fetch_holdings
