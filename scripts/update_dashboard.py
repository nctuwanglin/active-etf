#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台股主動式 ETF 儀表板更新主流程。

流程:偵測 ETF 清單 → 逐檔抓持股 → 判斷資料日/是否跳過 → 比對前日算異動
      → 抓收盤價 → 寫 history/active.json/perf_stats → 產生 index.html

守則(繼承 twse-disposition 教訓):
- 資料日取自抓回資料的眾數,絕不用系統時鐘判斷交易日。
- 單檔失敗標 stale 沿用前日持股,不中斷整批;全部失敗才 exit 1。
- 跳過更新時 log 明確印「跳過更新」(workflow 以此判讀,不能只看 exit code)。

用法:python3 scripts/update_dashboard.py [--force]
本機手動請走 scripts/run_local.sh(會先 pull + 跑測試)。
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crosslinks as crosslinks_mod
import outputs
import quotes as quotes_mod
import registry as registry_mod
import render_html
from adapters import base
from adapters import (allianz, capital, ctbc, fubon,  # noqa: F401 註冊 ADAPTERS
                      fuhhwa, kgi, nomura, president,
                      taishin)
from diffengine import compute_events

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY = DATA / "history"
REGISTRY_PATH = DATA / "etf_registry.json"
LAST_COUNTS = DATA / "last_counts.json"
PERF_STATS = DATA / "perf_stats.json"
ACTIVE_JSON = ROOT / "active.json"
INDEX_HTML = ROOT / "index.html"

TWSE_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"


def log(msg):
    print(msg, flush=True)


def fetch_registry():
    rows = base.get(TWSE_ALL).json()
    detected = registry_mod.detect_etfs(rows)
    reg = registry_mod.load_and_update(REGISTRY_PATH, detected)
    log("偵測 ETF {} 檔(台股型 {} 檔)".format(
        len(detected), sum(1 for e in detected if e["market"] == "tw")))
    unsupported = sorted(c for c, r in reg.items()
                         if r.get("market") == "tw" and r.get("status") == "unsupported")
    if unsupported:
        log("⚠️ 尚未支援的投信 ETF(需補 adapter):{}".format(", ".join(unsupported)))
    return reg


def fetch_all_holdings(reg):
    """回傳 {code: {status, data_date, holdings, meta}};失敗者不放入。"""
    results = {}
    for code, r in sorted(reg.items()):
        if r.get("market") != "tw" or r.get("status") != "active":
            continue
        fn = base.ADAPTERS.get(r.get("adapter"))
        if fn is None:
            log("  {} {}: adapter {} 未載入,跳過".format(code, r.get("name"), r.get("adapter")))
            continue
        try:
            data_date, holdings, meta = fn(r)
            results[code] = {"status": "ok", "data_date": data_date,
                             "holdings": holdings, "meta": meta or {}}
            log("  {} {}: {} 檔 @ {}".format(code, r.get("name"), len(holdings), data_date))
        except Exception as e:  # adapter 內任何錯誤都不該拖垮整批
            log("  ✗ {} {}: {}".format(code, r.get("name"), e))
    return results


def carry_stale(results, reg, prev_snapshot):
    """抓失敗的 ETF 沿用前日快照並標 stale(不產生事件)。"""
    if not prev_snapshot:
        return
    for code, r in sorted(reg.items()):
        if r.get("market") != "tw" or r.get("status") != "active":
            continue
        if code in results:
            continue
        prev = (prev_snapshot.get("etfs") or {}).get(code)
        if not prev or not prev.get("holdings"):
            continue
        holdings = [base.Holding(**h) for h in prev["holdings"]]
        results[code] = {"status": "stale", "data_date": prev.get("data_date"),
                         "holdings": holdings, "meta": {}}
        log("  ↺ {}: 沿用 {} 快照(標記 stale)".format(code, prev.get("data_date")))


def resolve_data_date(results):
    """各檔資料日取眾數(單一投信延遲不影響整體判定)。"""
    dates = [r["data_date"] for r in results.values()
             if r["status"] == "ok" and r.get("data_date")]
    if not dates:
        return None
    return collections.Counter(dates).most_common(1)[0][0]


def compute_all_events(results, prev_snapshot):
    if not prev_snapshot:
        log("無前日快照:首次執行,今日不產生異動事件")
        for r in results.values():
            r["events"] = []
        return
    prev_etfs = prev_snapshot.get("etfs") or {}
    total = 0
    for code, r in results.items():
        if r["status"] != "ok":
            r["events"] = []
            continue
        prev = prev_etfs.get(code)
        if not prev or not prev.get("holdings") or prev.get("data_date") == r.get("data_date"):
            r["events"] = []
            continue
        prev_map = {h["code"]: base.Holding(**h) for h in prev["holdings"]}
        curr_map = {h.code: h for h in r["holdings"]}
        r["events"] = compute_events(prev_map, curr_map)
        total += len(r["events"])
    log("異動事件合計 {} 筆".format(total))


def build_fundamentals(results, etf_quotes):
    """meta + ETF 市價 → 折溢價。"""
    out = {}
    for code, r in results.items():
        meta = dict(r.get("meta") or {})
        close = etf_quotes.get(code)
        nav = meta.get("nav_per_unit")
        meta["close"] = close
        meta["premium_pct"] = (round((close - nav) / nav * 100, 2)
                               if close and nav else None)
        out[code] = meta
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="跳過所有防呆")
    args = ap.parse_args()

    reg = fetch_registry()
    log("抓取持股:")
    results = fetch_all_holdings(reg)
    if not results:
        log("✗ 全部 ETF 抓取失敗,中止(不寫入任何檔案)")
        return 1

    data_date = resolve_data_date(results)
    if not data_date:
        log("✗ 無法判定資料日,中止")
        return 1
    log("資料日:{}".format(data_date))

    if not args.force and outputs.should_skip(data_date, LAST_COUNTS):
        log("跳過更新:資料日 {} 未新於上次已處理日".format(data_date))
        return 0

    counts = {c: len(r["holdings"]) for c, r in results.items() if r["status"] == "ok"}
    anomalies = outputs.check_anomaly(counts, LAST_COUNTS)
    if anomalies and not args.force:
        log("✗ 持股檔數驟降 >50%:{}(疑似解析錯誤,--force 可強制)".format(anomalies))
        return 1

    tw_weights = registry_mod.reclassify_by_holdings(REGISTRY_PATH, results)
    demoted = [c for c, w in sorted(tw_weights.items()) if w < registry_mod.TW_WEIGHT_MIN]
    if demoted:
        log("依實際持股改判為海外型(不列入台股型統計):{}".format(
            ", ".join("{} 台股僅{:.0f}%".format(c, tw_weights[c]) for c in demoted)))

    prev_snapshot = outputs.load_prev_snapshot(HISTORY, data_date)
    carry_stale(results, reg, prev_snapshot)
    compute_all_events(results, prev_snapshot)

    quote_date, all_quotes = quotes_mod.fetch_all()
    log("收盤價:{} 共 {} 檔".format(quote_date, len(all_quotes)))
    fundamentals = build_fundamentals(results, all_quotes)
    links = crosslinks_mod.fetch_crosslinks()
    log("交叉連結:處置中 {} 檔、研究筆記 {} 篇".format(
        len(links["dispo"]), len(links["notes"])))

    outputs.write_snapshot(data_date, results, HISTORY)
    outputs.append_events(PERF_STATS, data_date, results, all_quotes)
    active = outputs.build_active_json(data_date, reg, results, fundamentals, links,
                                       quotes=all_quotes)
    ACTIVE_JSON.write_text(
        json.dumps(active, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    INDEX_HTML.write_text(render_html.render(active, reg))
    outputs.update_last_counts(data_date, counts, LAST_COUNTS)
    log("完成:{} 檔 ETF、{} 檔個股反向索引".format(
        len(active["etfs"]), len(active["stocks"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
