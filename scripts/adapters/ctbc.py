# -*- coding: utf-8 -*-
"""中國信託投信(ctbcinvestments.com.tw)adapter。

資料源(2026-08-05 探勘):
- POST /API/home/AuthToken?token=www.ctbcinvestments.com  body {}
    回傳 Data.token(之後所有 API 以 querystring token 帶入)。
    注意:全站 API 回應可能是「JSON 字串」(雙層編碼),要 parse 兩次。
- POST /API/etf/ETFList?token=…  body {}
    Data.Data[] {ETF_ID, FID, …}(00406A ↔ E0038)。
- POST /API/etf/ETFHoldingWeight?token=…  body {"FID":"E0038","StartDate":"2026/08/05"}
    StartDate 必填;非交易日/未上傳回 ResultCode=1 → 逐日往回試(最多 7 天)。
    Data.FundAssets[0].資料日期 為資料日;FundAssetsDetail[Code=='STOCK'].Data[]
    {code_:'2330', name_, qty_:'610,000.00', weights_:'9.10'}(海外持股 code_ 形如
    'TSLA US',台股型基金為純數字代號)。
"""
import datetime
import json

from .base import ADAPTERS, AdapterError, Holding, post, validate_holdings

AUTH = "https://www.ctbcinvestments.com.tw/API/home/AuthToken"
ETFLIST = "https://www.ctbcinvestments.com.tw/API/etf/ETFList"
HOLDING = "https://www.ctbcinvestments.com.tw/API/etf/ETFHoldingWeight"

_token = None
_fund_map = None


def _decode(resp):
    d = resp.json()
    return json.loads(d) if isinstance(d, str) else d


def _get_token():
    global _token
    if _token is None:
        d = _decode(post(AUTH, params={"token": "www.ctbcinvestments.com"}, json={}))
        _token = d["Data"]["token"]
    return _token


def parse_etflist(d):
    rows = d["Data"]["Data"] if isinstance(d.get("Data"), dict) else d.get("Data", [])
    return {r["ETF_ID"]: r["FID"] for r in rows if r.get("ETF_ID")}


def parse_holding(d, etf_code):
    """ETFHoldingWeight 回應 → (data_date, [Holding]);失敗回 (None, None) 供重試。"""
    if d.get("ResultCode") != 0:
        return None, None
    data = d.get("Data") or {}
    assets = data.get("FundAssets") or []
    groups = [g for g in (data.get("FundAssetsDetail") or [])
              if g.get("Code") == "STOCK"]
    rows = groups[0].get("Data") or [] if groups else []
    if not assets or not rows:
        return None, None
    holdings = [Holding(code=str(r["code_"]).strip(), name=str(r["name_"]).strip(),
                        shares=int(float(r["qty_"].replace(",", ""))),
                        weight=float(r["weights_"]))
                for r in rows]
    data_date = assets[0]["資料日期"].replace("/", "-")
    return data_date, validate_holdings(holdings, etf_code)


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    tk = _get_token()
    if _fund_map is None:
        _fund_map = parse_etflist(_decode(post(ETFLIST, params={"token": tk}, json={})))
    if code not in _fund_map:
        raise AdapterError("ctbc: {} 不在 ETFList".format(code))
    fid = _fund_map[code]
    day = datetime.date.today()
    for back in range(8):
        q = (day - datetime.timedelta(days=back)).strftime("%Y/%m/%d")
        d = _decode(post(HOLDING, params={"token": tk},
                         json={"FID": fid, "StartDate": q}))
        data_date, holdings = parse_holding(d, code)
        if holdings:
            return data_date, holdings
    raise AdapterError("ctbc: {} 連續 8 日無持股資料".format(code))


ADAPTERS["ctbc"] = fetch_holdings
