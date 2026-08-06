# -*- coding: utf-8 -*-
"""野村投信(nomurafunds.com.tw)adapter。

資料源(2026-08-06 探勘):
- POST https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundTradeInfo
    body {"Type":1,"Keyword":"","FundNo":"00980A","Date":"2026-08-06"}
    無需 session/token,一般 UA 直接可取。
- Date 必須「恰好」是某個 PCF 公告日(營業日),未來日或假日回 Entries=null,
  故由今日逐日往回試(最多 7 天)。
- 回應 Entries:
    CNavDtStr        持股資料日 '2026/08/05'(CPcfdate 是公告日 T+1,不可用)
    Stocks[]         CStockCode/CStockName/CQuantity/CWeightsPct(已是百分比數值)
    CAnceTotalAv     基金淨資產     CAnceTotalIssues 已發行單位
    CAnceNav         每單位淨值(字串) CBeneficiariesCount 受益人數
"""
import datetime

from .base import (ADAPTERS, AdapterError, Holding, post, to_num,
                   validate_holdings)

TRADEINFO = "https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/GetFundTradeInfo"


def parse_tradeinfo(d, etf_code):
    """GetFundTradeInfo → (data_date, [Holding], meta);查無資料回三個 None 供重試。"""
    e = d.get("Entries")
    if not e:
        return None, None, None
    rows = e.get("Stocks") or []
    if not rows or not e.get("CNavDtStr"):
        return None, None, None
    holdings = [Holding(code=str(r["CStockCode"]).strip(),
                        name=str(r["CStockName"]).strip(),
                        shares=int(r["CQuantity"]),
                        weight=float(r["CWeightsPct"]))
                for r in rows]
    data_date = e["CNavDtStr"].replace("/", "-")
    meta = {"scale": to_num(e.get("CAnceTotalAv")),
            "units": to_num(e.get("CAnceTotalIssues")),
            "nav_per_unit": to_num(e.get("CAnceNav")),
            "holders": to_num(e.get("CBeneficiariesCount"))}
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    code = etf["code"]
    day = datetime.date.today()
    for back in range(8):
        q = (day - datetime.timedelta(days=back)).strftime("%Y-%m-%d")
        r = post(TRADEINFO, json={"Type": 1, "Keyword": "", "FundNo": code, "Date": q},
                 headers={"Content-Type": "application/json"})
        try:
            d = r.json()
        except ValueError:
            raise AdapterError("nomura: {} 回非 JSON(改版?)".format(code))
        data_date, holdings, meta = parse_tradeinfo(d, code)
        if holdings:
            return data_date, holdings, meta
    raise AdapterError("nomura: {} 連續 8 日無持股資料".format(code))


ADAPTERS["nomura"] = fetch_holdings
