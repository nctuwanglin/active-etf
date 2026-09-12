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
from adapters import (ab, allianz, capital, cathay,  # noqa: F401 註冊 ADAPTERS
                      ctbc, firstsec, fubon, fuhhwa, jpmorgan,
                      kgi, megafunds, nomura, president, sinopac,
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

# active.json 的 schema 版本。新增欄位採「相加不改名」,既有 key 語意不變,
# 下游(個人績效儀表板 dashlib/related.py)不需同步改版即可繼續運作。
SCHEMA_VERSION = 2


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


def carry_stale(results, reg, prev_snapshot, today_snapshot=None):
    """抓失敗的 ETF 沿用既有快照並標 stale(不產生事件)。

    **沿用來源取「前日快照」與「本日快照既有內容」中資料日較新的那一份。**
    只看前日會造成資料倒退:同一個資料日重跑時,若某檔這次抓失敗、但先前那次
    (例如 Actions)已經成功寫入較新的持股,只從前日複製會把好資料蓋成更舊的。
    2026-08-08 實際踩到:本機連不上野村,重跑把 Actions 抓到的 08-06 蓋回 08-05。
    """
    for code, r in sorted(reg.items()):
        if r.get("market") != "tw" or r.get("status") != "active":
            continue
        if code in results:
            continue
        cands = [s for s in ((today_snapshot or {}).get("etfs", {}).get(code),
                             (prev_snapshot or {}).get("etfs", {}).get(code))
                 if s and s.get("holdings")]
        if not cands:
            continue
        best = max(cands, key=lambda s: s.get("data_date") or "")
        holdings = [base.Holding(**h) for h in best["holdings"]]
        results[code] = {"status": "stale", "data_date": best.get("data_date"),
                         "holdings": holdings, "meta": best.get("meta") or {}}
        log("  ↺ {}: 沿用 {} 快照(標記 stale)".format(code, best.get("data_date")))


def reject_regressions(results, prev_snapshot):
    """抓取「成功但比既有快照更舊」時,退回既有快照並標 stale。

    carry_stale 只擋抓取失敗;投信偶爾會回一份舊快取(HTTP 200、內容完整),
    那種情況下持股會倒退,compute_events 還會算出方向相反的假事件——
    把「其實沒動」讀成大額賣出。日期沒有前進就一律不採用這次的結果。
    """
    prev_etfs = (prev_snapshot or {}).get("etfs") or {}
    for code, r in sorted(results.items()):
        if r.get("status") != "ok":
            continue
        prev = prev_etfs.get(code)
        if not prev or not prev.get("holdings"):
            continue
        pd_, cd = prev.get("data_date") or "", r.get("data_date") or ""
        if not (pd_ and cd) or cd >= pd_:
            continue
        r["holdings"] = [base.Holding(**h) for h in prev["holdings"]]
        r["data_date"] = pd_
        r["meta"] = prev.get("meta") or {}
        r["status"] = "stale"
        log("  ⚠ {}: 抓到較舊資料({} < {}),保留既有快照不倒退".format(code, cd, pd_))


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
        # 只有資料日「前進」才算事件。原本只排除相等,日期倒退時仍會比對,
        # 產生方向相反的假事件(見 NoDateRegressionTests)。
        pd_, cd = prev.get("data_date") or "", r.get("data_date") or ""
        if not prev.get("holdings") or not (pd_ and cd) or cd <= pd_:
            r["events"] = []
            continue
        prev_map = {h["code"]: base.Holding(**h) for h in prev["holdings"]}
        curr_map = {h.code: h for h in r["holdings"]}
        r["events"] = compute_events(prev_map, curr_map)
        total += len(r["events"])
    log("異動事件合計 {} 筆".format(total))


def build_fundamentals(results, etf_quotes, quote_date=None):
    """meta + ETF 市價 → 折溢價。**只在 NAV 日與收盤價日相同時才算折溢價。**

    舊版把 quote_date 丟掉,於是舊 NAV 配最新收盤價仍會產生精確到小數兩位的
    數字。實例:00980A 持股日 09-07、NAV 25.18,配 09-08 的 close 24.83 顯示
    −1.39%——那不是同日折溢價,卻長得像。日期不一致時寧可留白並說明原因。

    nav_date 若 adapter 沒給,以持股基準日為準:各投信的 PCF 是同一份文件
    同時公告 NAV 與持股,兩者基準日相同。
    """
    out = {}
    for code, r in results.items():
        meta = dict(r.get("meta") or {})
        close = etf_quotes.get(code)
        nav = meta.get("nav_per_unit")
        nav_date = meta.get("nav_date") or r.get("data_date")
        meta["nav_date"] = nav_date
        meta["close"] = close
        meta["quote_date"] = quote_date
        meta["premium_pct"] = None
        meta["premium_note"] = None
        if not (close and nav):
            pass
        elif quote_date and nav_date and quote_date != nav_date:
            meta["premium_note"] = "NAV {} 與收盤價 {} 非同日,不計折溢價".format(
                nav_date, quote_date)
        else:
            meta["premium_pct"] = round((close - nav) / nav * 100, 2)
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

    # 逐檔指紋比對:只有「每一檔的資料日、狀態、持股都與上次完全相同」才跳過。
    # 舊做法只比全域資料日眾數,補跑時單檔前進或 stale 恢復都會被誤跳過。
    if not args.force and outputs.should_skip_results(
            results, outputs.load_fingerprint(LAST_COUNTS)):
        log("跳過更新:逐檔資料與上次完全相同(資料日 {})".format(data_date))
        return 0

    counts = {c: len(r["holdings"]) for c, r in results.items() if r["status"] == "ok"}
    anomalies = outputs.check_anomaly(counts, LAST_COUNTS)
    if anomalies and not args.force:
        log("✗ 持股檔數驟降 >50%:{}(疑似解析錯誤,--force 可強制)".format(anomalies))
        return 1

    tw_weights = registry_mod.reclassify_by_holdings(REGISTRY_PATH, reg, results)
    demoted = [c for c, w in sorted(tw_weights.items()) if w < registry_mod.TW_WEIGHT_MIN]
    if demoted:
        log("依實際持股改判為海外型(不列入台股型統計):{}".format(
            ", ".join("{} 台股僅{:.0f}%".format(c, tw_weights[c]) for c in demoted)))

    prev_snapshot = outputs.load_prev_snapshot(HISTORY, data_date)
    # 同一資料日重跑時,本日既有快照可能比前日快照更新(見 carry_stale 說明)
    reject_regressions(results, prev_snapshot)
    carry_stale(results, reg, prev_snapshot,
                outputs.load_snapshot(HISTORY, data_date))
    compute_all_events(results, prev_snapshot)

    quote_date, all_quotes, quote_failed = quotes_mod.fetch_all()
    log("收盤價:{} 共 {} 檔{}".format(
        quote_date, len(all_quotes),
        "(來源失敗:{})".format("、".join(quote_failed)) if quote_failed else ""))
    fundamentals = build_fundamentals(results, all_quotes, quote_date)
    links = crosslinks_mod.fetch_crosslinks()
    log("交叉連結:處置中 {} 檔、研究筆記 {} 篇".format(
        len(links["dispo"]), len(links["notes"])))

    outputs.write_snapshot(data_date, results, HISTORY)
    outputs.append_events(PERF_STATS, data_date, results, all_quotes)
    active = outputs.build_active_json(data_date, reg, results, fundamentals, links,
                                       quotes=all_quotes)
    # 順序重要:schema_version 先入,build_id 才涵蓋完整內容
    active["schema_version"] = SCHEMA_VERSION
    active["build_id"] = render_html.build_id_of(active)
    # 產物一律原子寫入:中途失敗留下半截檔案的話,下游(績效儀表板)會直接解析失敗
    outputs.write_text_atomic(
        ACTIVE_JSON,
        json.dumps(active, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    outputs.write_text_atomic(INDEX_HTML, render_html.render(active, reg))
    outputs.update_last_counts(data_date, counts, LAST_COUNTS,
                               fingerprint=outputs.results_fingerprint(results))
    log("完成:{} 檔 ETF、{} 檔個股反向索引".format(
        len(active["etfs"]), len(active["stocks"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
