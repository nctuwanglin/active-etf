# 台股主動式 ETF 儀表板(第一階段)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上線 `nctuwanglin.github.io/active-etf`:每日自動抓取台股主動式 ETF 完整持股,計算異動,產出三分頁儀表板與 `active.json` 下游 API。

**Architecture:** 複製 twse-disposition 模式——`scripts/update_dashboard.py` 為主流程(registry 偵測 → adapter 抓持股 → diff → 寫 JSON/HTML),GitHub Actions cron 雙班,Pages 發佈。每家投信一個 adapter 模組,統一 `fetch_holdings()` 介面。

**Tech Stack:** Python 3.11+,只用 `requests`(個別投信若供 xlsx 再加 `openpyxl`);前端為腳本產生的自包含靜態 HTML(vanilla JS,無外部依賴)。

## Global Constraints

- 資料日一律從抓回的資料推導(PCF/持股頁上的資料日期),**絕不用系統時鐘**。
- `data/history/YYYY-MM-DD.json` 內容確定性:無執行時間戳,同日重跑產出相同 bytes。
- 單檔 ETF 抓取/驗證失敗 → 該檔標 `stale` 沿用前日快照,**不中斷整批**;全部失敗才 exit 1。
- 持股權重合計必須落在 95–105%(容忍現金),否則該檔視為失敗。
- UI 繁體中文,站內慣例**綠漲紅跌**。
- 海外型主動式 ETF(名稱含 美國/全球/日本/越南/世界)排除,registry 可手動覆寫 `market` 欄位。
- TWSE `STOCK_DAY_ALL` 端點 `response=json` 實際回 CSV(twse-disposition 已知坑),解析要用 csv。
- 每個 adapter 必須有 fixture 測資;tests 在 workflow 內先跑,失敗即不更新。

## 檔案結構(全貌)

```
scripts/update_dashboard.py   # 主流程(orchestration only,邏輯在模組)
scripts/registry.py           # ETF 清單偵測與 etf_registry.json 維護
scripts/adapters/base.py      # Holding、AdapterError、http session、validate_holdings
scripts/adapters/<issuer>.py  # president(統一)/fuhhwa(復華)/fubon(富邦)/capital(群益)/ctbc(中信)
scripts/diffengine.py         # 兩快照比對 → 事件
scripts/outputs.py            # history 快照、active.json、perf_stats 事件累積
scripts/render_html.py        # index.html 產生
scripts/quotes.py             # TWSE/TPEx 收盤價(事件日收盤、折溢價用)
scripts/run_local.sh          # pull + pytest + 執行
tests/fixtures/<issuer>/…     # 各投信真實回應存檔
tests/test_*.py
.github/workflows/update.yml
```

---

### Task 1: repo 基礎 + registry(ETF 清單自動偵測)

**Files:**
- Create: `scripts/registry.py`, `tests/test_registry.py`, `tests/fixtures/twse_stock_day_all.json`, `.gitignore`, `requirements.txt`(內容:`requests`、`pytest`)

**Interfaces:**
- Produces: `registry.detect_etfs(rows: list[dict]) -> list[dict]`(每項 `{code, name, market}`,market ∈ tw|foreign);`registry.load_and_update(path: Path, fetched: list[dict]) -> dict`(讀寫 etf_registry.json,回傳 registry dict;新代號自動加入,`status` 依 adapter 有無設 `active|unsupported`)。registry JSON 欄位:`code, name, issuer, adapter, market, status, listed_date, first_snapshot_date`。`ISSUER_BY_PREFIX`:由 ETF 名稱第 3–4 字推投信(如「主動統一…」→ `president`),對照表寫死於 registry.py。

- [ ] **Step 1:** 抓一次 `https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL` 存 `tests/fixtures/twse_stock_day_all.json`(只留 ETF 列以縮小檔案)。
- [ ] **Step 2:** 寫失敗測試:`test_detect_etfs_filters_00xxxA`(29 檔中含 00981A、排除 0050)、`test_foreign_classified`(00988A 主動統一全球創新 → foreign)、`test_registry_new_code_unsupported`(虛構 00998A 未知投信 → status=unsupported)。
- [ ] **Step 3:** 實作 `registry.py` 使測試通過:正則 `^00\d{3}A$`;`FOREIGN_KEYWORDS = ("美國","全球","日本","越南","世界")`;issuer 對照表涵蓋現有 16 家投信(統一/野村/群益/中信/安聯/復華/台新/元大/國泰/摩根/富邦/聯博/凱基/第一金/永豐/兆豐)。
- [ ] **Step 4:** `pytest tests/test_registry.py -v` 全過 → commit `feat: ETF registry 自動偵測`。

### Task 2: adapter 基礎層

**Files:**
- Create: `scripts/adapters/__init__.py`, `scripts/adapters/base.py`, `tests/test_base.py`

**Interfaces:**
- Produces: `@dataclass Holding {code:str, name:str, shares:int, weight:float}`(weight 為百分比數值,如 25.1);`class AdapterError(Exception)`;`get(url, **kw)`(共用 requests.Session、UA header、timeout=30、重試 2 次);`validate_holdings(holdings, etf_code) -> list[Holding]`(空 → raise AdapterError;權重合計不在 95–105 → raise;code 正規化為純代號字串);`ADAPTERS: dict[str, callable]` 註冊表,key 同 registry 的 adapter 欄位,value 為 `fetch_holdings(etf: dict) -> list[Holding]`。

- [ ] **Step 1:** 寫失敗測試:權重合計 80 → raise;空列表 → raise;合計 98.7(含現金)→ 通過;股票代號 `"2330 "` → 正規化 `"2330"`。
- [ ] **Step 2:** 實作 base.py,測試過 → commit `feat: adapter 基礎層`。

### Task 3–7: 五家投信 adapter(統一→復華→富邦→群益→中信)

每家同一套流程,以 Task 3 統一(president,00981A/00403A)為例;富邦已知入口 `https://websys.fsit.com.tw/FubonETF/Trade/Pcf.aspx`,其餘入口於 Step 1 探勘(統一 ezmoney.com.tw、復華 fhtrust.com.tw、群益 capitalfund.com.tw、中信 ctbcinvestments.com.tw)。

**Files(每家):**
- Create: `scripts/adapters/<issuer>.py`, `tests/test_adapter_<issuer>.py`, `tests/fixtures/<issuer>/holdings_<code>.{json|html|xlsx}`

**Interfaces:**
- Consumes: base.py 的 `Holding/AdapterError/get/validate_holdings`。
- Produces: `fetch_holdings(etf) -> list[Holding]` 並在 `ADAPTERS` 註冊;`data_date(raw) -> str`(從該投信回應解析資料日期 YYYY-MM-DD,持股頁一定有揭露日期)。

- [ ] **Step 1(探勘,一次性):** 瀏覽器開該投信 ETF 持股明細頁 → read_network_requests 找出實際資料端點(XHR JSON / Excel 下載 / HTML 表格)→ 用 curl 重現該請求(含必要 header/Referer)→ 原始回應存 `tests/fixtures/<issuer>/`,並把「端點 URL + 必要參數 + 格式」記在 adapter 檔頭註解。
- [ ] **Step 2:** 針對 fixture 寫失敗測試:解析出 >20 檔持股、含台積電 2330、權重合計 95–105、`data_date` 解析正確。
- [ ] **Step 3:** 實作 parser 使測試過。
- [ ] **Step 4:** 線上實抓 smoke test(`python3 -c` 一次性驗證,不進測試)確認與 fixture 同格式。
- [ ] **Step 5:** commit `feat: <issuer> adapter(涵蓋 <codes>)`。

### Task 8: 快照寫入 + 防呆狀態

**Files:**
- Create: `scripts/outputs.py`, `tests/test_outputs.py`

**Interfaces:**
- Consumes: `Holding`;registry dict。
- Produces: `write_snapshot(date, etf_results, history_dir) -> Path`(etf_results: `{code: {status, data_date, holdings, events}}`);`load_prev_snapshot(history_dir, before_date) -> dict|None`;`should_skip(data_date, last_counts_path) -> bool`(資料日 ≤ 上次已處理日 → True,log 印「跳過更新」);`update_last_counts(...)`(記 data_date 與各 ETF 檔數;單檔檔數對前次驟降 >50% → 該檔標 anomaly 併入 stale 邏輯)。

- [ ] **Step 1:** 失敗測試:同輸入重複呼叫產出相同 bytes;`should_skip` 三情境(新資料日/同日/舊資料日);驟降 50% 判定。
- [ ] **Step 2:** 實作、測試過、commit `feat: 快照與防呆狀態`。

### Task 9: diff engine(申購贖回等比例校正)

**Files:**
- Create: `scripts/diffengine.py`, `tests/test_diffengine.py`

**Interfaces:**
- Consumes: 兩份 `{code: Holding}`。
- Produces: `compute_events(prev, curr, shares_thr=0.05, weight_thr=0.1) -> list[dict]`,事件 `{code, name, type: ADD|REMOVE|INCREASE|DECREASE, shares_delta_pct, weight_delta, prev_weight, weight}`。

- [ ] **Step 1:** 失敗測試四情境:
  - 純申購:全部持股股數 +10%、權重不變 → **無事件**(等比例校正吸收)。
  - 加碼:規模效應 +10% 下某股 +20% → INCREASE。
  - 新增/剔除:昨無今有 → ADD;昨有今無 → REMOVE。
  - 門檻邊界:校正後 +4.9% → 無事件。
- [ ] **Step 2:** 實作:

```python
def compute_events(prev, curr, shares_thr=0.05, weight_thr=0.1):
    common = [c for c in curr if c in prev and prev[c].shares > 0]
    ratios = sorted(curr[c].shares / prev[c].shares for c in common)
    scale = ratios[len(ratios) // 2] if ratios else 1.0  # 中位數 = 申贖規模效應
    events = []
    for c, h in curr.items():
        if c not in prev:
            events.append(_ev(h, "ADD", None)); continue
        adj = h.shares / (prev[c].shares * scale) - 1 if prev[c].shares else 0
        dw = h.weight - prev[c].weight
        if adj >= shares_thr and dw >= weight_thr:
            events.append(_ev(h, "INCREASE", prev[c], adj))
        elif adj <= -shares_thr and dw <= -weight_thr:
            events.append(_ev(h, "DECREASE", prev[c], adj))
    for c, h in prev.items():
        if c not in curr:
            events.append(_ev(h, "REMOVE", h))
    return events
```

- [ ] **Step 3:** 測試過 → commit `feat: 異動判定引擎`。

### Task 10: 收盤價與事件庫(perf_stats)

**Files:**
- Create: `scripts/quotes.py`, Modify: `scripts/outputs.py`, Test: `tests/test_quotes.py`

**Interfaces:**
- Produces: `quotes.fetch_all() -> dict[code, {close, date}]`(TWSE STOCK_DAY_ALL 之 CSV 解析 + TPEx `tpex_mainboard_quotes` openapi,沿 twse-disposition 已驗證作法);`outputs.append_events(perf_stats_path, date, events_by_etf, quotes)`(事件庫追加 `{date, etf, code, type, close}`,同日重跑先去重)。

- [ ] Step 1 失敗測試(CSV fixture 解析、去重)→ Step 2 實作 → commit `feat: 收盤價與事件庫累積`。

### Task 11: active.json(下游契約)

**Files:**
- Modify: `scripts/outputs.py`, Test: `tests/test_active_json.py`; Create: `README.md`(schema 文件)

**Interfaces:**
- Produces: `build_active_json(registry, etf_results, quotes, fundamentals) -> dict`:

```json
{
  "updated": "2026-08-05",
  "etfs": {"00981A": {"name":…, "issuer":…, "status":"ok|stale|unsupported",
            "scale":…, "holders":…, "nav":…, "close":…, "premium_pct":…,
            "holdings":[{"code","name","shares","weight"}], "events":[…]}},
  "stocks": {"2330": {"name":"台積電", "total_weight":…,
              "etfs":[{"etf","weight","shares"}], "recent_events":[近10筆]}},
  "consensus": {"increase":[{"code","name","etfs":[…]}], "decrease":[…]}
}
```

- [ ] 失敗測試(反向索引正確聚合、consensus 需 ≥2 檔同向)→ 實作 → README 寫 schema 與範例 → commit `feat: active.json 下游 API`。

### Task 12: ETF 基本面(ETFortune ajax)

**Files:**
- Create: `scripts/fundamentals.py`, `tests/fixtures/etfortune/*.json`, Test: `tests/test_fundamentals.py`

**Interfaces:**
- Produces: `fetch_fundamentals(code) -> {scale, holders, nav, market_price, premium_pct} | None`(來源 `POST https://www.twse.com.tw/zh/ETFortune/ajaxEtfInfoChart`,回應形狀於 Step 1 抓 fixture 確認;失敗回 None 不影響主流程)。

- [ ] Step 1 瀏覽器抓 ajax 實際 request/response 存 fixture → Step 2 失敗測試 → Step 3 實作 → commit `feat: ETF 規模/受益人/折溢價`。

### Task 13: 主流程串接

**Files:**
- Create: `scripts/update_dashboard.py`, `scripts/run_local.sh`, Test: `tests/test_main_flow.py`(以 monkeypatch 假 adapter 跑整條)

**Interfaces:**
- Consumes: 前述所有模組。
- Produces: CLI `python3 scripts/update_dashboard.py [--force]`。流程:registry 更新 → 逐 ETF 抓持股(try/except → stale)→ 全體 data_date 取眾數,`should_skip` 判斷 → diff → quotes → fundamentals → 寫 history/active.json/perf_stats → render HTML。stale ETF 沿用前日 holdings 且不產生事件。**全部 ETF 失敗 → exit 1 不寫任何檔**。log 需含各 ETF 狀態一行與「跳過更新」字樣(workflow 驗證用)。

- [ ] 失敗測試(假 adapter 一成一敗 → 敗者 stale、批次成功;全敗 → exit 1)→ 實作 → commit `feat: 主流程`。

### Task 14: index.html 產生器(三分頁 UI)

**Files:**
- Create: `scripts/render_html.py`, Test: `tests/test_render.py`(產出含 AUTO:DATE、三分頁 nav、資料以 `const DATA = {…}` 內嵌)

**Interfaces:**
- Consumes: `build_active_json` 的 dict(直接內嵌為前端資料)。
- Produces: `render(active: dict, history_summary: list) -> str`。`<title>主動式ETF追蹤 | Updated YYYY-MM-DD</title>`;`<!-- AUTO:DATE:YYYY-MM-DD -->` 標記。

版面(自包含 vanilla JS + CSS,深色系沿 twse-disposition 風格,綠漲紅跌):
- **Tab1 今日異動**:共識榜置頂(≥2 檔同向)、事件總表(篩選:ETF 下拉、事件類型 chips、搜尋框——沿用 twse-disposition `applyFilter` 交集模式)。
- **Tab2 各檔 ETF**:每檔卡片(規模/受益人/折溢價/資料日 stale 標記)+ 前十大持股橫向長條(CSS width 百分比,不用圖表庫)+ 完整持股表(可展開)。
- **Tab3 個股反查**:搜尋 → 該股被持有明細表(ETF/權重/股數/近期事件)+ 共識持股排行 Top 30(被最多檔持有);個股列附外部連結:研究筆記(見 Task 15)與處置狀態 badge。
- 未支援 ETF 顯示灰色卡「已偵測,adapter 待補」。

- [ ] 測試(結構斷言,非像素)→ 實作 → 本機跑一次真資料、瀏覽器開啟目檢三分頁 → commit `feat: 三分頁儀表板 UI`。

### Task 15: 既有儀表板交叉連結

**Files:**
- Modify: `scripts/update_dashboard.py`, `scripts/render_html.py`, Test: `tests/test_crosslinks.py`

**Interfaces:**
- Produces: `fetch_crosslinks() -> {dispo: set[code], notes: dict[code, url]}`——dispo 讀 `https://nctuwanglin.github.io/twse-disposition/dispo.json`(取現行處置代碼,schema 注意同代碼多筆取 `period_end` 最大);notes 抓 `https://nctuwanglin.github.io/stock-research-notes/` 解析 index 連結、以檔名前綴股票代號建映射。抓取失敗 → 空集合,不影響主流程。

- [ ] fixture 測試 → 實作(Tab3/事件表中:處置中標紅 badge「處置」、有研究頁附「📝」連結)→ commit `feat: 處置股與研究筆記交叉連結`。

### Task 16: GitHub 發佈 + Actions 自動化

**Files:**
- Create: `.github/workflows/update.yml`

- [ ] **Step 1:** `gh repo create nctuwanglin/active-etf --public --source ~/active-etf --push`;repo Settings 啟用 Pages(main / root)。
- [ ] **Step 2:** workflow(cron `37 9 * * 1-5` + `17 12 * * 1-5`,錯峰值沿用 twse-disposition 實測):checkout → pip install → `pytest` → `python3 scripts/update_dashboard.py` → 有 diff 才 commit push → **Verify live deployment**(curl 線上 title 比對資料日;不符 → Pages API 觸發重建 → 等待重驗 → 空 commit → 仍失敗 exit 1),整段從 twse-disposition update.yml 移植改路徑。
- [ ] **Step 3:** `gh workflow run` 手動觸發一次,`gh run view --log` 確認實際輸出(不能只看 conclusion,twse-disposition 教訓),線上頁面驗證。
- [ ] **Step 4:** commit + 更新 memory(新 repo 記錄、reference-published-sites 加一筆)。

---

## Self-Review 紀錄

- Spec 覆蓋:規模前五投信 adapter(Task3–7)、diff(9)、三分頁(14)、active.json(11)、基本面(12)、共識榜(11/14)、perf 事件累積(10)、交叉連結(15)、自動化+驗證(16)、防呆(1/2/8/13)。第二階段項目(其餘投信、績效比較、回測 UI)不在本計畫。
- Adapter 端點無法預知格式,以「探勘→fixture→測試→實作」固定流程取代虛構程式碼,非 placeholder。
- 型別一致性:`Holding`/`fetch_holdings`/`etf_results`/事件 dict 各 task 引用一致。
