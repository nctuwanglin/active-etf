# -*- coding: utf-8 -*-
"""adapter 共用層:資料結構、HTTP 工具、持股驗證、adapter 註冊表。

每家投信 adapter 模組需提供 fetch_holdings(etf: dict) -> (data_date, [Holding])
並以 ADAPTERS["<name>"] = fetch_holdings 註冊(name 同 registry 的 adapter 欄位)。
"""
import time
from dataclasses import dataclass

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 主動式 ETF 現金/期貨部位可觀(實測 00403A 股票僅 84%),此檢查只為抓解析錯誤
# (權重尺度錯置、整批漏列),不是投資組合完整性檢查。
WEIGHT_SUM_MIN = 50.0
WEIGHT_SUM_MAX = 105.0


class AdapterError(Exception):
    """單檔 ETF 抓取/解析/驗證失敗。主流程捕捉後標 stale,不中斷整批。"""


@dataclass
class Holding:
    code: str
    name: str
    shares: int
    weight: float  # 百分比數值,如 25.1


_session = None


def get(url, **kw):
    """共用 GET:帶 UA、timeout、失敗重試 2 次。kw 透傳 requests(headers 會合併)。"""
    return _request("GET", url, **kw)


def post(url, **kw):
    return _request("POST", url, **kw)


def _request(method, url, **kw):
    global _session
    if _session is None:
        _session = requests.Session()
    headers = {"User-Agent": UA}
    headers.update(kw.pop("headers", {}))
    kw.setdefault("timeout", 30)
    last = None
    for attempt in range(3):
        try:
            r = _session.request(method, url, headers=headers, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise AdapterError("{} 抓取失敗: {}".format(url, last))


def validate_holdings(holdings, etf_code):
    """空資料/權重合計異常/負股數 → AdapterError;回傳代號正規化後的清單。"""
    if not holdings:
        raise AdapterError("{}: 持股為空".format(etf_code))
    total = sum(x.weight for x in holdings)
    if not (WEIGHT_SUM_MIN <= total <= WEIGHT_SUM_MAX):
        raise AdapterError("{}: 權重合計 {:.2f} 超出 {}-{}".format(
            etf_code, total, WEIGHT_SUM_MIN, WEIGHT_SUM_MAX))
    out = []
    for x in holdings:
        code = x.code.strip().upper()
        if x.shares < 0:
            raise AdapterError("{}: {} 股數為負".format(etf_code, code))
        out.append(Holding(code=code, name=x.name.strip(), shares=int(x.shares),
                           weight=float(x.weight)))
    return out


def parse_dotnet_date(s):
    """解析 .NET JSON 日期,兩種形式都出現過:
    '2026-08-04T00:00:00' 或 '/Date(1785772800000)/'(ms epoch,UTC)。
    回傳 'YYYY-MM-DD'。"""
    import datetime
    import re as _re
    m = _re.match(r"/Date\((\d+)\)/", s)
    if m:
        # ms 值實測為台灣午夜之 epoch(如 1785772800000 → 2026-08-04 00:00 台北)
        # 用 UTC 解會少一天,必須以 +8 時區解
        tz = datetime.timezone(datetime.timedelta(hours=8))
        dt = datetime.datetime.fromtimestamp(int(m.group(1)) / 1000, tz)
        return dt.strftime("%Y-%m-%d")
    return s[:10]


def roc_date(dt):
    """datetime.date → 民國年字串 '115/08/05'"""
    return "{}/{:02d}/{:02d}".format(dt.year - 1911, dt.month, dt.day)


# adapter 註冊表:模組 import 時自行填入
ADAPTERS = {}
