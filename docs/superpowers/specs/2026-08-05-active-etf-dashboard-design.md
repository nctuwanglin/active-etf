# 台股主動式 ETF 每日追蹤儀表板 — 設計文件

日期:2026-08-05
狀態:已與使用者確認設計方向,待實作計畫

## 目的

每日追蹤全部台股主動式 ETF 的持股,提供:

1. 每日持股異動(新增/剔除/加碼/減碼)
2. 每檔 ETF 的持股比例分佈
3. 個股反向查詢:某股票被哪些主動式 ETF 持有、各佔多少
4. 供下游儀表板(個人家庭績效儀表板、stock-research-notes)以 JSON 查詢
5. 公開發佈於 GitHub Pages:`https://nctuwanglin.github.io/active-etf/`

## 已確認的範圍決策

- **追蹤範圍**:全部投資台股的主動式 ETF(代號 `00xxxA`),自動偵測新掛牌;債券型(`D` 結尾)與海外型排除。
- **歷史資料**:從上線日開始累積,不回填。異動資料自上線次日起產生。
- **資料源**:各投信官網每日揭露之持股明細/PCF,逐家投信寫 adapter;不依賴第三方彙整站。
- **額外功能全數納入第一版**:經理人共識榜、ETF 基本面追蹤、加碼後表現回測(資料先行、UI 待累積)、與既有儀表板交叉連結。

## 整體架構

複製 twse-disposition 已驗證模式:Python 更新腳本重寫靜態 index.html + 輸出結構化 JSON,GitHub Actions cron 盤後自動執行,GitHub Pages 發佈。

```
active-etf/
├── index.html                  # 儀表板(每日由腳本重寫,含 AUTO:DATE 標記)
├── active.json                 # 最新完整資料,下游儀表板讀取(隨 Pages 發佈)
├── scripts/
│   ├── update_dashboard.py     # 主流程:偵測清單 → 抓持股 → 算異動 → 寫 JSON/HTML
│   ├── adapters/               # 每家投信一個 parser,統一介面
│   │   ├── base.py             # 介面定義與共用工具(下載、重試、快取)
│   │   └── <issuer>.py         # 野村、統一、群益、中信、復華…
│   └── run_local.sh            # 本機手動:先 git pull + 跑測試再執行
├── data/
│   ├── etf_registry.json       # ETF 總表(代號→名稱→投信→adapter→狀態)
│   ├── history/YYYY-MM-DD.json # 每交易日全 ETF 持股快照(內容確定性、無時間戳)
│   ├── perf_stats.json         # 加碼/減碼事件後 N 日表現快取
│   └── last_counts.json        # 防呆狀態檔(上次處理日期、各 ETF 持股檔數)
├── tests/test_adapters.py      # 每個 adapter 配 fixture 測資,workflow 內先跑
├── docs/superpowers/specs/     # 設計文件
└── .github/workflows/update.yml
```

## 元件設計

### 1. ETF 清單自動偵測(registry)

- 每次執行先從 TWSE 官方來源(ISIN 清單或 OpenAPI ETF 報表,實作時擇穩定者)取得所有掛牌 ETF,篩出代號符合 `00\d{3}A` 者。
- 與 `data/etf_registry.json` 比對:
  - 新掛牌且投信已有 adapter → 自動納入追蹤。
  - 新掛牌但投信無 adapter → registry 記為 `unsupported`,儀表板顯示「已偵測、尚未支援」,workflow log 輸出明確警告。新檔永不靜默漏掉。
- registry 欄位:`code, name, issuer, adapter, status(active|unsupported|delisted), listed_date, first_snapshot_date`。

### 2. Adapter 層

- 統一介面:`fetch_holdings(etf: dict) -> list[Holding]`,`Holding = {stock_code, stock_name, shares, weight}`。
- 每家投信一個模組,處理該投信官網的格式(Excel 下載/內嵌 JSON/HTML 表格各異)。
- 防呆(繼承 twse-disposition 慣例):
  - 權重合計須在 95%–105% 區間(容忍現金部位),否則該檔標記失敗。
  - 空資料即失敗;**單檔 ETF 失敗不中斷整批**,該檔沿用前一日快照並標 `stale`,其餘照常更新。
  - 單檔持股檔數對前一日驟降 >50% 即標記異常待人工確認,`--force` 可跳過。
  - **資料日一律從抓回的資料推導,不用系統時鐘**(2026-07-14 twse-disposition 教訓)。跳過更新的判斷用「資料日 vs last_counts.json 上次已處理日」。
- 建置順序:按投信管理規模分批,先寫覆蓋大部分資產的前 4–5 家,其餘依偵測警告陸續補。

### 3. 異動判定(diff engine)

比對最近兩份快照,對每檔 ETF 的每檔持股產生事件:

- **新增(ADD)**:昨無今有。**剔除(REMOVE)**:昨有今無。
- **加碼(INCREASE)/減碼(DECREASE)**:股數變化經「基金規模等比例校正」後超過門檻。
  - 校正:ETF 申購/贖回使全部持股股數等比例增減,屬資金流而非經理人操作。以該 ETF 全體持股股數變化的中位數比例當作規模效應基準,個股偏離基準超過門檻才算主動加減碼。
  - 權重變化同時記錄供顯示,但權重受股價漲跌被動影響,不做主判定依據。
  - 門檻初始值:校正後股數變化 ≥5% 且權重變化 ≥0.1 個百分點;寫成常數可調。
- 事件寫入當日 history 快照與 `active.json`,並累積至 `perf_stats.json` 的事件庫(事件日、個股、事件日收盤價)。

### 4. 輸出

- **`active.json`**(下游 API 契約,schema 寫進 README):
  - `updated`(資料日)、`etfs`(每檔:基本資料、規模、受益人數、折溢價、完整持股與權重、今日事件)
  - `stocks`(**以個股代號為 key 的反向索引**:被哪些 ETF 持有、各檔權重、合計權重、近期事件)——下游 O(1) 查詢
  - `consensus`(今日多檔同步加碼/減碼榜)
- **`data/history/YYYY-MM-DD.json`**:當日全 ETF 持股快照 + 事件,僅交易日寫入,內容確定性(無執行時間戳)。
- **`index.html`**:重寫產生,`<title>` 含資料日供部署驗證。

### 5. 儀表板 UI(單頁三分頁,站內慣例綠漲紅跌)

- **Tab 1 今日異動**:全 ETF 新增/剔除/加碼/減碼總表,篩選(ETF、個股、事件類型、搜尋框);共識異動榜置頂(今日被 ≥2 檔同步加碼/減碼之個股)。
- **Tab 2 各檔 ETF**:每檔持股分佈(前十大長條 + 產業分佈)、規模、受益人數、淨值 vs 市價折溢價、上市以來績效 vs 0050/加權指數。
- **Tab 3 個股反向查詢**:輸入代號/名稱 → 被哪些 ETF 持有、各檔權重與近期加減碼紀錄;共識持股排行(被最多檔持有/合計權重最高);連結 stock-research-notes 既有研究頁、處置股狀態 badge(讀 twse-disposition 的 dispo.json)。
- **加碼後表現**(Tab 1 或 3 內區塊):事件後 5/20 日個股表現統計。資料自上線日累積,累積約一個月前 UI 顯示「資料累積中」。

### 6. 自動化(GitHub Actions)

- cron 錯峰雙班(沿用 twse-disposition 實測值):`37 9 * * 1-5`(台灣 17:37 主跑)+ `17 12 * * 1-5`(20:17 補跑)。
- 流程:跑 tests → 執行 update_dashboard.py → 有變更才 commit push → **Verify live deployment**(比對線上 title 資料日,失敗自動觸發 Pages API 重建 → 空 commit → 仍失敗才亮紅燈)。
- 非交易日/資料未更新即跳過(依資料日判斷,log 明確輸出「跳過更新」字樣)。

### 7. 與既有儀表板整合

- 本儀表板讀 `dispo.json`(處置股 badge)。
- 績效儀表板 `dashlib/related.py` 與 stock-research-notes 新增讀 `https://nctuwanglin.github.io/active-etf/active.json`(個股在主動式 ETF 的持倉佔比/近期異動 badge)。下游改動不在本 repo 範圍,待本站上線穩定後另行處理。

## 錯誤處理總覽

| 情境 | 行為 |
|---|---|
| 單一投信官網掛掉/改版 | 該投信旗下 ETF 標 stale 沿用昨日快照,其餘照常;workflow 警告 |
| 全部來源失敗 | exit 1,不寫任何資料 |
| 新投信無 adapter | registry 標 unsupported,UI 顯示待支援,log 警告 |
| 非交易日/資料未更新 | 依資料日判斷跳過,不蓋錯日期 |
| Pages 部署卡住 | 自動 API 重建補救(繼承既有機制) |

## 測試

- `tests/test_adapters.py`:每個 adapter 配真實回應的 fixture 檔,驗證解析結果 schema 與權重合計。
- diff engine 單元測試:ADD/REMOVE/加減碼判定、申購贖回等比例校正情境。
- workflow 內先跑測試再執行更新。

## 分期

- **第一階段(上線)**:registry 偵測、前 4–5 大投信 adapter、diff engine、三分頁 UI(含基本面欄位:規模/受益人數/折溢價)、共識榜、active.json、perf_stats 事件累積、workflow 自動化。
- **第二階段**:補齊其餘投信 adapter、績效 vs 0050/大盤比較、加碼後表現 UI 啟用(資料累積約一個月後)。
- **第三階段**:下游兩儀表板接入 active.json。

## 風險

1. 各投信官網改版會弄壞個別 adapter → 單檔失敗不擋整批 + fixture 測試,壞哪家修哪家。
2. 上線前歷史不可得 → 接受,從上線日累積。
3. 10+ 家 adapter 建置量大 → 按規模分批,偵測機制保證未支援者可見。
