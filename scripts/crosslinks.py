# -*- coding: utf-8 -*-
"""與既有儀表板的交叉連結:處置股狀態、個股研究筆記。

抓取失敗一律回空(不影響主流程)——交叉連結是加值資訊,不該讓外站拖垮更新。
"""
import re

from adapters.base import AdapterError, get

DISPO_JSON = "https://nctuwanglin.github.io/twse-disposition/dispo.json"
NOTES_INDEX = "https://nctuwanglin.github.io/stock-research-notes/"
NOTES_BASE = "https://nctuwanglin.github.io/stock-research-notes/"

# 研究筆記檔名慣例:<代號>-<slug>.html(如 2330-tsmc-event.html)
NOTE_HREF_RE = re.compile(r'href="((\d{4})-[a-z0-9-]+\.html)"')


def parse_dispo(doc):
    """dispo.json → 現行處置中代碼集合。

    schema 注意:active 是「處置紀錄」列表,同一代碼可有多筆重疊處置,
    此處只需代碼集合,不必取 period_end 最大者。"""
    return {str(r.get("code")) for r in (doc.get("active") or []) if r.get("code")}


def parse_notes(index_html):
    """研究筆記 index → {代號: 完整網址}"""
    return {code: NOTES_BASE + fn for fn, code in NOTE_HREF_RE.findall(index_html)}


def fetch_crosslinks():
    dispo, notes = set(), {}
    try:
        dispo = parse_dispo(get(DISPO_JSON).json())
    except (AdapterError, ValueError, KeyError):
        pass
    try:
        notes = parse_notes(get(NOTES_INDEX).text)
    except (AdapterError, ValueError):
        pass
    return {"dispo": sorted(dispo), "notes": notes}
