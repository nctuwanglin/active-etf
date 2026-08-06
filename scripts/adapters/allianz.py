# -*- coding: utf-8 -*-
"""安聯投信(etf.allianzgi.com.tw)adapter。

與野村同一套 ETF 網站供應商(端點名 GetFundTradeInfo 相同),但三處不同:
1. base path 是 /webapi/api/ 而非 /API/ETFAPI/api/
2. 需 anti-forgery token,且 header 名為 X-XSRF-TOKEN
   (X-CSRF-TOKEN / RequestVerificationToken 都回 400,2026-08-06 實測)
3. 持股不在 Stocks[],而在通用表格結構 DynamicTableData:
     {"TableTitle": "股票 (95.60%)",
      "Rows": [["1","2330","台積電","518,000","12.54%"], …]}
   欄序為 [序號, 代號, 名稱, 股數, 權重],值都是已格式化字串。

流程:
- GET  /list-trade                                建立 session cookie
- GET  /webapi/api/AntiForgery/GetAntiForgeryToken 取 token
- POST /webapi/api/Category/GetFundTypeDropdownOptions {}  找「主動式」類別 Id
- POST /webapi/api/Category/GetFundDropdownOptions {"TypeId": <Id>}
       → SecuritiesCode(00993A)↔ FundNo(E0002)對照
- POST /webapi/api/Fund/GetFundTradeInfo
       {"Type":1,"Keyword":"","FundNo":"E0002","Date":"2026-08-06"}
  Date 須為實際 PCF 公告日,假日/未來日回無資料 → 逐日往回試(最多 7 天)。
"""
import datetime

from .base import (ADAPTERS, AdapterError, Holding, get, post, to_num,
                   validate_holdings)

BASE = "https://etf.allianzgi.com.tw"
PAGE = BASE + "/list-trade"
TOKEN_URL = BASE + "/webapi/api/AntiForgery/GetAntiForgeryToken"
FUNDTYPES = BASE + "/webapi/api/Category/GetFundTypeDropdownOptions"
FUNDLIST = BASE + "/webapi/api/Category/GetFundDropdownOptions"
TRADEINFO = BASE + "/webapi/api/Fund/GetFundTradeInfo"

_token = None
_fund_map = None


def _headers():
    return {"Content-Type": "application/json", "X-XSRF-TOKEN": _get_token(),
            "Referer": PAGE}


def _get_token():
    global _token
    if _token is None:
        get(PAGE)  # 先建立 session cookie,token 與 cookie 綁定
        _token = get(TOKEN_URL).json()["token"]
    return _token


def parse_fund_map(d):
    """GetFundDropdownOptions → {'00993A': 'E0002', …}(略過無代號的佔位列)。"""
    return {(e.get("SecuritiesCode") or "").strip(): e["FundNo"]
            for e in d.get("Entries") or [] if (e.get("SecuritiesCode") or "").strip()}


def pick_active_type_id(d):
    """從基金類別清單挑「主動式」那一類的 Id(硬編 6 會在對方調整分類時默默失效)。"""
    for e in d.get("Entries") or []:
        if "主動" in (e.get("Name") or ""):
            return e["Id"]
    raise AdapterError("allianz: 基金類別找不到「主動式」(改版?)")


def parse_tradeinfo(d, etf_code):
    """GetFundTradeInfo → (data_date, [Holding], meta);查無資料回三個 None 供重試。"""
    e = d.get("Entries")
    if not e:
        return None, None, None
    tables = [t for t in (e.get("DynamicTableData") or [])
              if (t.get("TableTitle") or "").startswith("股票")]
    if not tables or not e.get("CNavDt"):
        return None, None, None
    holdings = []
    for row in tables[0].get("Rows") or []:
        if len(row) < 5:
            continue
        _, code, name, shares, weight = row[:5]
        holdings.append(Holding(code=str(code).strip(), name=str(name).strip(),
                                shares=int(str(shares).replace(",", "")),
                                weight=float(str(weight).rstrip("%"))))
    if not holdings:
        return None, None, None
    data_date = e["CNavDt"][:10]
    meta = {"scale": to_num(e.get("CAnceTotalAv")),
            "units": to_num(e.get("CAnceTotalIssues")),
            "nav_per_unit": to_num(e.get("CAnceNav")),
            "holders": to_num(e.get("CBeneficiariesCount"))}
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    global _fund_map
    code = etf["code"]
    if _fund_map is None:
        type_id = pick_active_type_id(post(FUNDTYPES, json={}, headers=_headers()).json())
        _fund_map = parse_fund_map(
            post(FUNDLIST, json={"TypeId": type_id}, headers=_headers()).json())
    if code not in _fund_map:
        raise AdapterError("allianz: {} 不在基金清單".format(code))
    fund_no = _fund_map[code]
    day = datetime.date.today()
    for back in range(8):
        q = (day - datetime.timedelta(days=back)).strftime("%Y-%m-%d")
        r = post(TRADEINFO, headers=_headers(),
                 json={"Type": 1, "Keyword": "", "FundNo": fund_no, "Date": q})
        try:
            d = r.json()
        except ValueError:
            raise AdapterError("allianz: {} 回非 JSON(改版?)".format(code))
        data_date, holdings, meta = parse_tradeinfo(d, code)
        if holdings:
            return data_date, holdings, meta
    raise AdapterError("allianz: {} 連續 8 日無持股資料".format(code))


ADAPTERS["allianz"] = fetch_holdings
