# -*- coding: utf-8 -*-
"""聯博投信(abfunds.com.tw)adapter。

資料源(2026-08-07 探勘):公開 JSON API,base https://webapi.alliancebernstein.com/
以 **ISIN** 當基金識別(不是 ETF 代號):
- GET /v2/funds/tw/zh-tw/investor/<ISIN>/basket
    asOfDate(持股基準日)、nav、aum、shares、sharesPerBasket、announcementDate。
- GET /v2/funds/tw/zh-tw/investor/<ISIN>/holdings?date=<basket 的 asOfDate>
    domesticHoldings[] 依 holdingCategory 分段,只取 holdings-section-equity;
    每列 {holdingCode, holding, holdingShares, holdingPerc}。

ISIN 不用查表,可直接由代號算出:body = "TW000" + 代號,再補一碼 ISIN 檢查碼
(字元轉 36 進位展開後跑 Luhn)。已用兩個已知值驗證:
00404A → TW00000404A5、00980D → TW00000980D8。

兩個要注意的地方:
1. holdings 不帶 date 會回「最新一份」,其 asOfDate 可能比 basket 新一天
   (公告日 vs 基準日)。官網自己也是先拿 basket 的 asOfDate 再帶進 holdings,
   這裡照做,讓持股與基本面對在同一天。
2. 回應含 futures / options 分段(期貨那段權重高達 16%),**只能取 equity**,
   混進去權重合計會爆掉。
"""
from .base import (ADAPTERS, AdapterError, Holding, get, to_num,
                   validate_holdings)

BASE = "https://webapi.alliancebernstein.com/v2/funds/tw/zh-tw/investor/{}"
EQUITY = "holdings-section-equity"


def isin_check_digit(body):
    """ISIN 檢查碼:字母轉 36 進位數值展開後跑 Luhn。"""
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - total % 10) % 10)


def isin_for(etf_code):
    body = "TW000" + etf_code
    return body + isin_check_digit(body)


def parse_holdings(payload, etf_code):
    """holdings 回應 → (data_date, [Holding]);只取 equity 分段。"""
    sections = [s for s in (payload.get("domesticHoldings") or [])
                if s.get("holdingCategory") == EQUITY]
    if not sections:
        raise AdapterError("{}: holdings 無 equity 分段".format(etf_code))
    sec = sections[0]
    rows = sec.get("holdings") or []
    holdings = []
    for r in rows:
        code = str(r.get("holdingCode") or "").strip()
        shares = to_num(r.get("holdingShares"))
        weight = to_num(r.get("holdingPerc"))
        if not code or shares is None or weight is None:
            continue
        holdings.append(Holding(code=code, name=str(r.get("holding") or "").strip(),
                                shares=int(shares), weight=weight))
    d = (sec.get("asOfDate") or "").strip()  # 'MM/DD/YYYY'
    parts = d.split("/")
    if len(parts) != 3:
        raise AdapterError("{}: holdings 日期格式非預期 {!r}".format(etf_code, d))
    data_date = "{}-{}-{}".format(parts[2], parts[0], parts[1])
    return data_date, validate_holdings(holdings, etf_code)


def parse_basket(payload):
    return {"scale": to_num(payload.get("aum")),
            "units": to_num(payload.get("shares")),
            "nav_per_unit": to_num(payload.get("nav")),
            "holders": None}  # 端點不揭露受益人數


def fetch_holdings(etf):
    code = etf["code"]
    base = BASE.format(isin_for(code))
    try:
        basket = get(base + "/basket").json()
    except ValueError:
        raise AdapterError("ab: {} basket 回非 JSON".format(code))
    as_of = (basket.get("asOfDate") or "").strip()
    params = {"date": as_of} if as_of else None
    try:
        payload = get(base + "/holdings", params=params).json()
    except ValueError:
        raise AdapterError("ab: {} holdings 回非 JSON".format(code))
    data_date, holdings = parse_holdings(payload, code)
    return data_date, holdings, parse_basket(basket)


ADAPTERS["ab"] = fetch_holdings
