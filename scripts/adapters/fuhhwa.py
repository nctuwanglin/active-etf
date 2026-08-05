# -*- coding: utf-8 -*-
"""復華投信(fhtrust.com.tw)adapter。

資料源(2026-08-05 探勘):
- GET https://www.fhtrust.com.tw/api/fundList?ec001=3
    ETF 清單;etf002=股票代號 ↔ fundID(如 00991A ↔ ETF23)。
- GET https://www.fhtrust.com.tw/api/assets?fundID=ETF23&qDate=2026/08/05
    result[0].detail[] 持股(ftype='股票':stockid/stockname/qshare 千分位字串/
    prate_addaccint '14.638%');result[0].dDate 為資料日。
    非交易日/未來日回 dDate=None、detail 空 → 逐日往回試(最多 7 天)。
"""
import datetime

from .base import ADAPTERS, AdapterError, Holding, get, validate_holdings

FUNDLIST = "https://www.fhtrust.com.tw/api/fundList?ec001=3"
ASSETS = "https://www.fhtrust.com.tw/api/assets"

_fund_map = None


def parse_fund_map(fundlist_json):
    return {(f.get("etf002") or "").strip(): f["fundID"]
            for f in fundlist_json.get("result", []) if f.get("etf002")}


def parse_assets(d, etf_code):
    """assets 回應 → (data_date, [Holding]);detail 空回 (None, None) 供重試。"""
    results = d.get("result") or []
    if not results:
        return None, None
    r = results[0]
    detail = r.get("detail") or []
    rows = [x for x in detail if x.get("ftype") == "股票" and (x.get("stockid") or "").strip()]
    if not rows or not r.get("dDate"):
        return None, None
    holdings = [Holding(code=x["stockid"], name=x["stockname"],
                        shares=int(x["qshare"].replace(",", "")),
                        weight=float(x["prate_addaccint"].rstrip("%")))
                for x in rows]
    data_date = r["dDate"].replace("/", "-")
    return data_date, validate_holdings(holdings, etf_code)


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    if _fund_map is None:
        _fund_map = parse_fund_map(get(FUNDLIST).json())
    if code not in _fund_map:
        raise AdapterError("fuhhwa: {} 不在 fundList".format(code))
    fund_id = _fund_map[code]
    day = datetime.date.today()
    for back in range(8):
        q = (day - datetime.timedelta(days=back)).strftime("%Y/%m/%d")
        d = get(ASSETS, params={"fundID": fund_id, "qDate": q}).json()
        data_date, holdings = parse_assets(d, code)
        if holdings:
            return data_date, holdings
    raise AdapterError("fuhhwa: {} 連續 8 日無持股資料".format(code))


ADAPTERS["fuhhwa"] = fetch_holdings
