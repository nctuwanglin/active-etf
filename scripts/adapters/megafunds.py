# -*- coding: utf-8 -*-
"""兆豐投信(megafunds.com.tw)adapter。

網域是 **megafunds.com.tw**;我一開始試的 mifund.com.tw 根本不是兆豐投信,
所以曾誤判成「這家連不上」。

資料源(2026-08-06 探勘):
- ASP.NET WebForms 頁 https://www.megafunds.com.tw/MEGA/etf/trade_pcf.aspx
  基金切換是 POST 回原頁(不吃 querystring,`?fund_id=23` 會被忽略並回預設基金)。
  流程:GET 取 hidden 欄位 → POST(hidden + fund_id + button1)。

**hidden 欄位一定要整包原封帶回**(__VIEWSTATE / __VIEWSTATEGENERATOR /
__VIEWSTATEENCRYPTED)。我第一次自己挑欄位、還補了一個空的 __EVENTVALIDATION,
POST 回來是一張沒有任何持股列的頁面——不會報錯,只是靜默變空,很難察覺。

基金對照:下拉選項是「兆豐台灣豐收主動式ETF基金」,registry 名稱是
「主動兆豐台灣豐收」。去掉「主動」前綴後即為選項的前綴,以此對照,不硬編 id。
抓回後再用頁面上的「股票代號：00996A」複核,對不上就報錯。

資料日:頁面「查詢日期」是公告生效日(T+1),其後第一個日期才是持股基準日(T),
與國泰同樣的語意。頁面不揭露受益人數。
"""
import html
import re

from .base import (ADAPTERS, AdapterError, Holding, get, post, to_num,
                   validate_holdings)

PCF_URL = "https://www.megafunds.com.tw/MEGA/etf/trade_pcf.aspx"
PREFIX = "ctl00$ContentPlaceHolder1$"

HIDDEN_RE = re.compile(
    r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"')
OPTION_RE = re.compile(
    r'name="' + re.escape(PREFIX) + r'fund_id"[^>]*>(.*?)</select>', re.S)
ROW_RE = re.compile(
    r'<tr class="tr-stock">\s*<td[^>]*>\s*([0-9A-Z]{4,6})\s*</td>\s*'
    r'<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>\s*'
    r'<td[^>]*>\s*([\d.]+)%\s*</td>')
QUERY_DATE_RE = re.compile(r"查詢日期[^0-9]{0,40}(\d{4}/\d{2}/\d{2})")
DATE_RE = re.compile(r"\d{4}/\d{2}/\d{2}")


def parse_fund_map(page_html):
    """下拉 → {'兆豐台灣豐收主動式ETF基金': '23', …}"""
    t = html.unescape(page_html)
    m = OPTION_RE.search(t)
    if not m:
        raise AdapterError("megafunds: 找不到基金下拉(改版?)")
    return {name.strip(): val
            for val, name in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>',
                                        m.group(1)) if name.strip()}


def pick_fund_id(fund_map, etf_name):
    """registry 名稱「主動兆豐台灣豐收」→ 去前綴後當選項前綴比對。"""
    base = etf_name[2:] if etf_name.startswith("主動") else etf_name
    for name, fid in fund_map.items():
        if name.startswith(base):
            return fid
    return None


def parse_result(page_html, etf_code):
    """POST 後的結果頁 → (data_date, [Holding], meta)"""
    t = html.unescape(page_html)
    if etf_code not in t:
        raise AdapterError("{}: 結果頁不含此代號(基金對照錯誤?)".format(etf_code))
    # 標題與日期之間夾著多層標籤,一定要先去標籤再找,否則永遠找不到
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    m = QUERY_DATE_RE.search(plain)
    if not m:
        raise AdapterError("{}: 找不到查詢日期(改版?)".format(etf_code))
    # 查詢日期是公告生效日;其後第一個日期才是持股基準日
    after = DATE_RE.findall(plain[m.end():m.end() + 1200])
    data_date = (after[0] if after else m.group(1)).replace("/", "-")
    holdings = [Holding(code=c, name=n, shares=int(s.replace(",", "")),
                        weight=float(w))
                for c, n, s, w in ROW_RE.findall(t)]

    def val(label):
        mm = re.search(re.escape(label) + r"\s*(?:TWD\$)?\s*([\d,]+(?:\.\d+)?)", plain)
        return to_num(mm.group(1)) if mm else None

    meta = {"scale": val("基金淨資產價值(元)"),
            "units": val("已發行受益權單位總數"),
            "nav_per_unit": val("每受益權單位淨資產價值(元)"),
            "holders": None}  # 頁面不揭露受益人數
    return data_date, validate_holdings(holdings, etf_code), meta


def fetch_holdings(etf):
    code, name = etf["code"], (etf.get("name") or "").strip()
    page = get(PCF_URL).text
    fund_id = pick_fund_id(parse_fund_map(page), name)
    if not fund_id:
        raise AdapterError("megafunds: {}「{}」不在基金下拉".format(code, name))
    # hidden 欄位整包帶回,少一個就靜默回空頁
    data = dict(HIDDEN_RE.findall(page))
    data[PREFIX + "category_id"] = ""
    data[PREFIX + "fund_id"] = fund_id
    data[PREFIX + "button1"] = "查 詢"
    r = post(PCF_URL, data=data, headers={"Referer": PCF_URL})
    return parse_result(r.text, code)


ADAPTERS["megafunds"] = fetch_holdings
