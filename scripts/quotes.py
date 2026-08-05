# -*- coding: utf-8 -*-
"""上市/上櫃全股收盤價(ETF 折溢價、事件日收盤用)。

作法移植自 twse-disposition(已驗證):
- TWSE STOCK_DAY_ALL:response=json 實際回 CSV(2026-07 起),欄位
  0=日期(民國7碼) 1=代號 3=成交股數 8=收盤價 → 用 csv 解析。
- TPEx openapi tpex_mainboard_quotes:JSON,Date 為民國 7 碼。
"""
import csv
import io

from adapters.base import get

TWSE_STOCK_DAY = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"


def _roc_to_iso(roc7):
    return "{}-{}-{}".format(int(roc7[:3]) + 1911, roc7[3:5], roc7[5:7])


def parse_twse_csv(text):
    """回傳 (date_iso, {code: close})"""
    date_iso, out = None, {}
    for r in csv.reader(io.StringIO(text)):
        if len(r) < 11 or not (r[0].isdigit() and len(r[0]) == 7):
            continue
        if date_iso is None:
            date_iso = _roc_to_iso(r[0])
        code = r[1].strip()
        try:
            out[code] = float(r[8].replace(",", ""))
        except (ValueError, IndexError):
            continue
    return date_iso, out


def parse_tpex_json(rows):
    """回傳 (date_iso, {code: close})"""
    date_iso, out = None, {}
    for r in rows:
        code = (r.get("SecuritiesCompanyCode") or "").strip()
        if not code:
            continue
        d = (r.get("Date") or "").strip()
        if date_iso is None and len(d) == 7 and d.isdigit():
            date_iso = _roc_to_iso(d)
        try:
            out[code] = float((r.get("Close") or "").replace(",", ""))
        except ValueError:
            continue
    return date_iso, out


def fetch_all():
    """合併上市+上櫃收盤 → (date_iso, {code: close})。日期以 TWSE 為準。"""
    date_iso, quotes = parse_twse_csv(get(TWSE_STOCK_DAY).text)
    tpex_date, tpex = parse_tpex_json(get(TPEX_QUOTES).json())
    for code, close in tpex.items():
        quotes.setdefault(code, close)
    return date_iso or tpex_date, quotes
