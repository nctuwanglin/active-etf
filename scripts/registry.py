# -*- coding: utf-8 -*-
"""ETF 清單自動偵測與 etf_registry.json 維護。

資料源:TWSE OpenAPI STOCK_DAY_ALL(全部上市證券,含 ETF)。
台股主動式 ETF 代號規則:00xxxA(第 6 碼 A=股票型主動式;D=債券型不納入)。
新掛牌若投信已有 adapter 自動納入;未知投信標 unsupported,UI 顯示待支援。
registry 檔內的 market/status 等欄位可手動覆寫,重跑不會蓋掉既有值。
"""
import json
import re
from pathlib import Path

CODE_RE = re.compile(r"^00\d{3}A$")

# 名稱含這些關鍵字視為海外型,排除於追蹤(registry 可手動覆寫 market)。
# "ARK":00983A 主動中信ARK創新名稱無地區字樣但實持美股(2026-08-05 實查)。
FOREIGN_KEYWORDS = ("美國", "全球", "日本", "越南", "世界", "印度", "ARK")

# ETF 名稱一律「主動<投信><系列名>」,以投信名前綴對照 adapter 模組名
ISSUER_ADAPTERS = [
    ("統一", "president"),
    ("野村", "nomura"),
    ("群益", "capital"),
    ("中信", "ctbc"),
    ("安聯", "allianz"),
    ("復華", "fuhhwa"),
    ("台新", "taishin"),
    ("元大", "yuanta"),
    ("國泰", "cathay"),
    ("摩根", "jpmorgan"),
    ("富邦", "fubon"),
    ("聯博", "ab"),
    ("凱基", "kgi"),
    ("第一金", "firstsec"),
    ("永豐", "sinopac"),
    ("兆豐", "megafunds"),
]

# 第一階段已實作的 adapter(其餘投信標 unsupported,陸續補)
IMPLEMENTED_ADAPTERS = {"president", "fuhhwa", "fubon", "capital", "ctbc",
                        "nomura"}


def _classify(name):
    for kw in FOREIGN_KEYWORDS:
        if kw in name:
            return "foreign"
    return "tw"


def _issuer_adapter(name):
    base = name[2:] if name.startswith("主動") else name  # 去「主動」前綴
    for issuer, adapter in ISSUER_ADAPTERS:
        if base.startswith(issuer):
            return issuer, adapter
    return "", ""


def detect_etfs(rows):
    """從 STOCK_DAY_ALL 列資料篩出主動式 ETF。回傳 [{code,name,market,issuer,adapter}]"""
    out = []
    for r in rows:
        code = (r.get("Code") or "").strip()
        if not CODE_RE.match(code):
            continue
        name = (r.get("Name") or "").strip()
        issuer, adapter = _issuer_adapter(name)
        out.append({
            "code": code,
            "name": name,
            "market": _classify(name),
            "issuer": issuer,
            "adapter": adapter,
        })
    return out


def load_and_update(path, fetched):
    """讀取並更新 registry 檔。新代號加入;既有代號只補缺漏欄位,不覆寫。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reg = json.loads(path.read_text()) if path.exists() else {}
    for e in fetched:
        code = e["code"]
        if code in reg:
            for k, v in e.items():  # 只補新欄位(如改名不覆寫手動值)
                reg[code].setdefault(k, v)
            continue
        issuer = e.get("issuer", "")
        adapter = e.get("adapter", "")
        if not (issuer and adapter):
            issuer, adapter = _issuer_adapter(e.get("name", ""))
        entry = dict(e)
        entry["issuer"] = issuer
        entry["adapter"] = adapter
        entry["status"] = "active" if adapter in IMPLEMENTED_ADAPTERS else "unsupported"
        entry.setdefault("first_snapshot_date", None)
        reg[code] = entry
    path.write_text(json.dumps(reg, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return reg
