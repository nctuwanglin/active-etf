# -*- coding: utf-8 -*-
"""國泰投信(cathaysite.com.tw)adapter。

資料源(2026-08-06 探勘):公開 JSON API,base https://cwapi.cathaysite.com.tw/api/
- GET ETF/GetETFList?FundType=&PerPageCount=9999&status=1
    取 stockCode(00400A)↔ fundCode 對照。**內部 fundCode 是「EA」這種兩碼代號,
    不是 ETF 代號**,所有後續查詢都要用它。
- GET BuySale/GetBuySale?FundCode=EA&IsTest=false&status=1
    PCF 表頭:date(公告生效日,T+1)、preDateC(持股基準日,T)、aum、totUnit、
    basketUnit、nav、benefiCount(受益人數)。
- GET BuySale/GetStocksList?FundCode=EA&SearchDate=<date>&IsTest=false&status=1
    成分股與 basketShares(每申購買回基數的股數)。
- GET ETF/GetIndexStockWeights?fundCode=EA&status=1
    date + 每檔權重(與上面 PCF 同一組成分股,實測代號完全對齊)。

**股數是換算出來的,但換算的兩個數字都是官方公告值**:國泰公告的是「每基數股數」
而非總持股,總股數 = basketShares × (totUnit / basketUnit)。這是 PCF 的標準還原
方式,不是估計。唯一的精度限制來自 basketShares 取整——小部位(如每基數 13 股)
會有 ±2% 的量化誤差,但 diffengine 的門檻是股數變化 ≥5%,不會被這個誤差觸發。

踩過的坑:
1. 參數名是 **FundCode / SearchDate(大寫開頭)**,而且 SearchDate 必填;用小寫
   fundCode 或不帶日期,GetStocksList 會回「空陣列 + success:true」,看起來像
   這檔沒有成分股,其實是參數錯了。
2. 國泰自家 ETF 詳情頁對 00400A 是壞的(SPA 路由會吃掉網址參數第一個字元,把
   00400A 打成 0400A → 查無資料)。那是他們的 bug,不代表沒有資料。
3. 資料日取 preDateC(基準日)而非 date(公告日),才與其他投信的語意一致。
"""
from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

BASE = "https://cwapi.cathaysite.com.tw/api/"
ETF_LIST = BASE + "ETF/GetETFList"
BUYSALE = BASE + "BuySale/GetBuySale"
STOCKS = BASE + "BuySale/GetStocksList"
WEIGHTS = BASE + "ETF/GetIndexStockWeights"

_fund_map = None


def _result(resp, what):
    try:
        d = resp.json()
    except ValueError:
        raise AdapterError("cathay: {} 回非 JSON".format(what))
    if not d.get("success"):
        raise AdapterError("cathay: {} 失敗 {}".format(what, d.get("returnMessage")))
    return d.get("result")


def parse_fund_map(list_json):
    """GetETFList → {'00400A': 'EA', …}"""
    rows = list_json if isinstance(list_json, list) else (list_json or {}).get("list") or []
    return {(r.get("stockCode") or "").strip(): r["fundCode"]
            for r in rows if r.get("stockCode") and r.get("fundCode")}


def build_holdings(stocks, weights_rows, baskets, etf_code):
    """basketShares × 流通基數 → 總股數,與官方權重併成 Holding。"""
    wmap = {r["stockCode"]: to_num(r["weights"]) for r in weights_rows}
    holdings = []
    for r in stocks:
        code = str(r["prod"]).strip()
        if code not in wmap:
            continue  # 權重表沒有的(實測兩邊完全對齊,留著防單邊改版)
        # basketShares 破千會帶千分位('1,419'),直接 float() 會炸
        basket_shares = to_num(r["basketShares"])
        if basket_shares is None:
            continue
        shares = int(round(basket_shares * baskets))
        holdings.append(Holding(code=code, name=str(r["prodName"]).strip(),
                                shares=shares, weight=wmap[code]))
    if not holdings:
        raise AdapterError("{}: PCF 與權重表無交集(參數或改版?)".format(etf_code))
    return holdings


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    if _fund_map is None:
        _fund_map = parse_fund_map(
            _result(get(ETF_LIST, params={"FundType": "", "PerPageCount": 9999,
                                          "status": 1}), "GetETFList"))
    fund_code = _fund_map.get(code)
    if not fund_code:
        raise AdapterError("cathay: {} 不在 GetETFList".format(code))

    bs = _result(get(BUYSALE, params={"FundCode": fund_code, "IsTest": "false",
                                      "status": 1}), "GetBuySale")
    tot, basket = to_num(bs.get("totUnit")), to_num(bs.get("basketUnit"))
    if not (tot and basket):
        raise AdapterError("{}: PCF 缺流通單位數/基數,無法還原股數".format(code))

    stocks = _result(get(STOCKS, params={"FundCode": fund_code,
                                         "SearchDate": bs["date"],
                                         "IsTest": "false", "status": 1}),
                     "GetStocksList") or []
    w = _result(get(WEIGHTS, params={"fundCode": fund_code, "status": 1}),
                "GetIndexStockWeights") or {}
    rows = w.get("stockWeights") or []
    if not stocks or not rows:
        raise AdapterError("{}: PCF 成分股或權重表為空".format(code))

    holdings = build_holdings(stocks, rows, tot / basket, code)
    # 基準日用 preDateC(持股基準日),不是 date(公告生效日,會多一天)
    data_date = (bs.get("preDateC") or w.get("date") or "").replace("/", "-")
    if not data_date:
        raise AdapterError("{}: 取不到基準日".format(code))
    meta = {"scale": to_num(bs.get("aum")), "units": tot,
            "nav_per_unit": to_num(bs.get("nav")),
            "holders": to_num(bs.get("benefiCount"))}
    return data_date, validate_holdings(holdings, code), meta


ADAPTERS["cathay"] = fetch_holdings
