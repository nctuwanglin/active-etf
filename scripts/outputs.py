# -*- coding: utf-8 -*-
"""輸出層:每日快照(history)、防呆狀態(last_counts)、事件庫(perf_stats)、
active.json(下游 API)。所有檔案內容確定性——不含執行時間戳,同輸入同 bytes。
"""
import json
from pathlib import Path


def _dump(obj, path):
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def holdings_to_json(holdings):
    return [{"code": h.code, "name": h.name, "shares": h.shares,
             "weight": h.weight} for h in holdings]


def write_snapshot(date, etf_results, history_dir):
    """etf_results: {code: {status, data_date, holdings(list of Holding), events}}"""
    history_dir = Path(history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    doc = {"date": date, "etfs": {}}
    for code, r in sorted(etf_results.items()):
        doc["etfs"][code] = {
            "status": r["status"],
            "data_date": r.get("data_date"),
            "holdings": holdings_to_json(r.get("holdings") or []),
            "events": r.get("events") or [],
        }
    path = history_dir / "{}.json".format(date)
    _dump(doc, path)
    return path


def load_prev_snapshot(history_dir, before_date):
    """回傳 before_date(不含)之前最近一份快照 dict,無則 None。"""
    history_dir = Path(history_dir)
    if not history_dir.exists():
        return None
    candidates = sorted(p.stem for p in history_dir.glob("*.json")
                        if p.stem < before_date)
    if not candidates:
        return None
    return json.loads((history_dir / (candidates[-1] + ".json")).read_text())


def should_skip(data_date, last_counts_path):
    """資料日 ≤ 上次已處理日 → True(呼叫端須 log「跳過更新」)。"""
    p = Path(last_counts_path)
    if not p.exists():
        return False
    last = json.loads(p.read_text()).get("data_date", "")
    return bool(data_date and last and data_date <= last)


def check_anomaly(counts, last_counts_path):
    """單檔持股檔數對上次驟降 >50% → 該檔列入異常名單。counts: {etf: n}"""
    p = Path(last_counts_path)
    if not p.exists():
        return []
    prev = json.loads(p.read_text()).get("counts", {})
    bad = []
    for etf, n in counts.items():
        pn = prev.get(etf)
        if pn and n < pn * 0.5:
            bad.append(etf)
    return bad


def update_last_counts(data_date, counts, last_counts_path):
    _dump({"data_date": data_date, "counts": counts}, last_counts_path)


def append_events(perf_stats_path, date, etf_results, quotes):
    """把當日事件(含事件日收盤價)去重後追加進事件庫。"""
    p = Path(perf_stats_path)
    doc = json.loads(p.read_text()) if p.exists() else {"events": []}
    seen = {(e["date"], e["etf"], e["code"], e["type"]) for e in doc["events"]}
    for etf, r in sorted(etf_results.items()):
        for ev in r.get("events") or []:
            key = (date, etf, ev["code"], ev["type"])
            if key in seen:
                continue
            seen.add(key)
            doc["events"].append({
                "date": date, "etf": etf, "code": ev["code"],
                "type": ev["type"], "close": quotes.get(ev["code"]),
            })
    _dump(doc, p)
    return doc


def build_active_json(date, registry, etf_results, fundamentals, crosslinks=None,
                      quotes=None):
    """下游 API 主檔。schema 見 README。"""
    crosslinks = crosslinks or {}
    quotes = quotes or {}
    etfs, stocks, cons_inc, cons_dec = {}, {}, {}, {}
    for code, reg in sorted(registry.items()):
        if reg.get("market") != "tw":
            continue
        r = etf_results.get(code)
        f = (fundamentals or {}).get(code) or {}
        entry = {
            "name": reg.get("name"), "issuer": reg.get("issuer"),
            "status": (r or {}).get("status", reg.get("status", "unsupported")),
            "data_date": (r or {}).get("data_date"),
            "scale": f.get("scale"), "holders": f.get("holders"),
            "nav": f.get("nav_per_unit"), "close": f.get("close"),
            "premium_pct": f.get("premium_pct"),
            "holdings": holdings_to_json((r or {}).get("holdings") or []),
            "events": (r or {}).get("events") or [],
        }
        etfs[code] = entry
        for h in entry["holdings"]:
            s = stocks.setdefault(h["code"], {
                "name": h["name"], "total_weight": 0.0, "total_shares": 0,
                "etfs": [], "recent_events": []})
            # total_weight 是各檔權重「相加」,跨基金相加無量綱意義,只當熱度指標;
            # 要比較個股被主動式 ETF 持有的實際規模請用 total_value(股數×收盤價)。
            s["total_weight"] = round(s["total_weight"] + h["weight"], 4)
            s["total_shares"] += h["shares"]
            s["etfs"].append({"etf": code, "weight": h["weight"],
                              "shares": h["shares"]})
        for ev in entry["events"]:
            s = stocks.setdefault(ev["code"], {
                "name": ev["name"], "total_weight": 0.0, "total_shares": 0,
                "etfs": [], "recent_events": []})
            s["recent_events"].append({"etf": code, "type": ev["type"],
                                       "date": date})
            if ev["type"] in ("INCREASE", "ADD"):
                cons_inc.setdefault(ev["code"], {"name": ev["name"], "etfs": []})["etfs"].append(code)
            elif ev["type"] in ("DECREASE", "REMOVE"):
                cons_dec.setdefault(ev["code"], {"name": ev["name"], "etfs": []})["etfs"].append(code)
    for scode, s_ in stocks.items():
        px = quotes.get(scode)
        s_["close"] = px
        s_["total_value"] = round(s_["total_shares"] * px) if px else None
        s_["etf_count"] = len(s_["etfs"])
    consensus = {
        "increase": [{"code": c, **v} for c, v in sorted(cons_inc.items())
                     if len(v["etfs"]) >= 2],
        "decrease": [{"code": c, **v} for c, v in sorted(cons_dec.items())
                     if len(v["etfs"]) >= 2],
    }
    return {"updated": date, "etfs": etfs, "stocks": stocks,
            "consensus": consensus, "crosslinks": crosslinks}
