# -*- coding: utf-8 -*-
"""第一金投信(fsitc.com.tw)adapter。

資料源(2026-08-06 探勘):ASP.NET WebForms 頁 + jQuery WebMethod。
- POST https://www.fsitc.com.tw/WebAPI.aspx/Get_hd
    body {"pStrFundID":"183","pStrDate":"<yyyy-mm-dd 或空字串>"}
    回 {"d": "<JSON 字串>"}(**雙層編碼,要 parse 兩次**),每列:
      {fundid, sdate, group:"1", A:代號, B:名稱, C:權重, D:股數}
    pStrDate 給空字串就回最新一份,且 **sdate 本身就是持股基準日**
    (不像其他家要自己從公告日往回推)。
- POST WebAPI.aspx/Get_BuySellA 同樣參數,回基金淨資產/單位數等表頭。

**基金 ID 對照沒有可查的清單端點**:FundList/ETFList 兩頁的基金清單都是前端
渲染,靜態 HTML 裡沒有連結,站上也沒有列出基金的 WebMethod。唯一可靠的來源是
FundDetail.aspx?ID=<n> 頁面裡的「股票代號」欄位。因此:
  1. 優先用 registry 內快取的 source_id(第一次跑完就會寫回 etf_registry.json);
  2. 沒有才掃描 ID 區間反查,找到就寫回 etf 字典由主流程存檔。
詳情頁有 4.9MB,但「股票代號」出現在前 2%(約 111KB),所以掃描時用 stream 只讀
前 300KB 就中斷,不會真的拉滿整頁。
"""
import json
import re

from .base import (ADAPTERS, AdapterError, Holding, get, post, to_num,
                   validate_holdings)

WEBAPI = "https://www.fsitc.com.tw/WebAPI.aspx/"
DETAIL = "https://www.fsitc.com.tw/FundDetail.aspx"

# 反查掃描區間。**刻意開很窄**:每個 ID 都要拉一次詳情頁(前 300KB),掃 100 個
# ID 實測會跑到逾時,不能當常態路徑。已知 ID(2026-08-06:00408A=183、
# 00994A=182)已寫進 etf_registry.json 的 source_id,正常情況根本不會進來掃。
# 新掛牌的第一金 ETF 會拿到比現有更大的 ID,所以只往上掃一小段就夠;真的掃不到
# 會報錯要求手動補 source_id,而不是默默拖垮整批。
SCAN_HI, SCAN_LO = 200, 180
PEEK_BYTES = 300_000

CODE_RE = re.compile(r"股票代號</td>\s*<td[^>]*>\s*([0-9A-Z]{5,6})\s*</td>")


def _call(method, fund_id, date=""):
    r = post(WEBAPI + method,
             json={"pStrFundID": str(fund_id), "pStrDate": date},
             headers={"Content-Type": "application/json; charset=utf-8",
                      "Referer": "{}?ID={}".format(DETAIL, fund_id)})
    try:
        d = r.json()
        return json.loads(d["d"])  # 雙層編碼
    except (ValueError, KeyError, TypeError):
        raise AdapterError("firstsec: {} 回應非預期格式".format(method))


def peek_stock_code(fund_id):
    """只讀詳情頁前段,取出該 ID 對應的 ETF 代號;取不到回 None。"""
    r = get(DETAIL, params={"ID": fund_id}, stream=True)
    try:
        buf = b""
        for chunk in r.iter_content(32768):
            buf += chunk
            if len(buf) >= PEEK_BYTES:
                break
    finally:
        r.close()
    m = CODE_RE.search(buf.decode("utf-8", "replace"))
    return m.group(1) if m else None


def discover_fund_id(etf_code):
    for fid in range(SCAN_HI, SCAN_LO - 1, -1):
        try:
            if peek_stock_code(fid) == etf_code:
                return str(fid)
        except AdapterError:
            continue
    return None


def parse_hd(rows, etf_code):
    """Get_hd 回傳列 → (data_date, [Holding])。group=='1' 才是股票。"""
    stocks = [r for r in rows if str(r.get("group")) == "1" and (r.get("A") or "").strip()]
    if not stocks:
        raise AdapterError("{}: Get_hd 無股票明細".format(etf_code))
    holdings = []
    for r in stocks:
        shares = to_num(r.get("D"))
        weight = to_num(r.get("C"))
        if shares is None or weight is None:
            continue
        holdings.append(Holding(code=str(r["A"]).strip(), name=str(r["B"]).strip(),
                                shares=int(shares), weight=weight))
    date = (stocks[0].get("sdate") or "").strip()
    if not date:
        raise AdapterError("{}: Get_hd 無資料日".format(etf_code))
    return date[:10], validate_holdings(holdings, etf_code)


def parse_meta(rows):
    """Get_BuySellA 的 A/B 欄位配對 → 基本面。"""
    kv = {(r.get("A") or "").strip(): r.get("B") for r in rows}

    def pick(*labels):
        for k, v in kv.items():
            if any(k.startswith(l) for l in labels):
                return to_num(str(v).replace("TWD", ""))
        return None

    return {"scale": pick("基金淨資產價值"),
            "units": pick("已發行受益權單位總數"),
            "nav_per_unit": pick("每受益權單位淨資產價值"),
            "holders": None}  # 端點不揭露受益人數


def fetch_holdings(etf):
    code = etf["code"]
    fund_id = etf.get("source_id")
    if not fund_id:
        fund_id = discover_fund_id(code)
        if not fund_id:
            raise AdapterError(
                "firstsec: {} 在 ID {}-{} 掃不到對應基金;請到 FundDetail.aspx 找出"
                "該檔的 ID,手動填進 data/etf_registry.json 的 source_id"
                .format(code, SCAN_LO, SCAN_HI))
        etf["source_id"] = fund_id  # 寫回 registry,下次直接用
    data_date, holdings = parse_hd(_call("Get_hd", fund_id), code)
    try:
        meta = parse_meta(_call("Get_BuySellA", fund_id))
    except AdapterError:
        meta = None  # 基本面抓不到不影響持股主資料
    return data_date, holdings, meta


ADAPTERS["firstsec"] = fetch_holdings
