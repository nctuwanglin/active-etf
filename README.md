# 台股主動式 ETF 每日追蹤

線上儀表板：<https://nctuwanglin.github.io/active-etf/>

每個交易日自動抓取各投信公告的申購買回清單（PCF），彙整台股主動式 ETF 的
**每日持股異動、持股比例分佈、個股反向查詢**，並以 `active.json` 提供下游查詢。

## 三個主要視圖

| 分頁 | 內容 |
|---|---|
| 今日異動 | 全 ETF 的新增／剔除／加碼／減碼明細，含「經理人共識榜」（2 檔以上同方向調整的標的） |
| 各檔 ETF | 每檔規模、受益人數、淨值、折溢價、前十大持股權重條 |
| 個股反查 | 個股被哪些主動式 ETF 持有、各檔權重、合計持股市值、近期異動 |

## 資料來源與時序

持股一律取自**各投信官網公告的 PCF**（一手官方資料，非第三方彙整站）。
每家投信一個 adapter，統一回傳 `(資料日, 持股清單, 基本面)`。

**各家的資料日不一定同一天**：多數投信於交易日早上公告 PCF，內容是前一交易日收盤的持股（資料日 T-1）；
但部分投信（凱基、台新、中信）盤後就更新為當日持股（資料日 T）。
因此同一次執行抓回來的持股，各檔的 `data_date` 可能相差一天。

這不會造成錯誤的異動：每檔 ETF 只跟**自己**的前一份快照比對，且資料日沒變就不產生事件。
儀表板頁首顯示的資料日取各檔的眾數。`data/history/` 每個交易日留一份快照。

**加碼／減碼的判定**扣除了申購買回造成的等比例增減——ETF 被大量申購時所有持股股數會同步放大，
那是資金流不是經理人決策。判定以權重變化為主訊號，並以整體持股股數變化校正倍率。

## 涵蓋範圍

ETF 清單由 TWSE `STOCK_DAY_ALL` 自動偵測（代號 `00xxxA`），新掛牌自動納入：

- 投信已有 adapter → 自動開始追蹤
- 未知投信 → 標記 `unsupported`，儀表板明列「尚未支援」，不會靜默漏掉

「台股型／海外型」以**實際持股中台股代號的權重合計**判定（≥50% 為台股型），
不靠基金名稱猜——例如 00990A 主動元大AI新經濟名稱看不出來，實際美股 61%、台股僅 18%。

目前已實作 adapter：統一、復華、富邦、群益、中信、野村。

## 下游 API：`active.json`

隨 GitHub Pages 發佈於 <https://nctuwanglin.github.io/active-etf/active.json>，
內容確定性（不含執行時間戳，同輸入同 bytes）。

```jsonc
{
  "updated": "2026-08-05",          // 資料日（非執行日）
  "etfs": {
    "00981A": {
      "name": "主動統一台股增長", "issuer": "統一",
      "status": "ok",                // ok | stale（沿用前日）| unsupported
      "data_date": "2026-08-05",
      "scale": 307018000000.0,       // 基金淨資產（元）
      "holders": 1052004,            // 受益人數
      "nav": 28.58,                  // 每受益權單位淨值
      "close": 28.84,                // ETF 收盤價
      "premium_pct": 0.91,           // 折溢價 %（正為溢價）
      "holdings": [{"code": "2330", "name": "台積電",
                    "shares": 12134000, "weight": 9.5}],
      "events": [{"code": "2330", "name": "台積電", "type": "INCREASE",
                  "weight_delta": 0.42, "shares_delta": 500000}]
    }
  },
  "stocks": {                        // 個股反向索引（目標：O(1) 反查）
    "2330": {
      "name": "台積電",
      "etf_count": 11,               // 被幾檔主動式 ETF 持有
      "total_shares": 36123000,      // 合計持股股數
      "total_value": 43347600000,    // 合計持股市值（股數 × 收盤價，元）
      "total_weight": 104.676,       // 各檔權重相加，僅作熱度指標（跨基金相加無量綱意義）
      "close": 1200.0,
      "etfs": [{"etf": "00981A", "weight": 9.5, "shares": 12134000}],
      "recent_events": [{"etf": "00981A", "type": "INCREASE", "date": "2026-08-05"}]
    }
  },
  "consensus": {                     // 2 檔以上 ETF 同方向調整
    "increase": [{"code": "3017", "name": "奇鋐", "etfs": ["00981A", "00991A"]}],
    "decrease": []
  },
  "crosslinks": {                    // 與既有儀表板的交叉引用
    "dispo": ["8046"],               // 處置中個股（來自 twse-disposition）
    "notes": {"2330": "2330-tsmc-event.html"}  // stock-research-notes 研究頁
  }
}
```

事件型別：`ADD`（新增）、`REMOVE`（剔除）、`INCREASE`（加碼）、`DECREASE`（減碼）。

### 下游使用建議

比較「個股被主動式 ETF 持有的規模」請用 `total_value`；`total_weight` 是各檔百分比直接相加，
只適合當熱度排序，不要當成真實比例解讀。

## 本機執行

```bash
scripts/run_local.sh
```

會先 `git pull --rebase`、跑測試，再執行更新腳本（直接跑 `update_dashboard.py`
容易與 GitHub Actions 產生分岔）。`--force` 可跳過所有防呆。

## 自動更新

`.github/workflows/update.yml` 每個營業日跑兩班（台灣 09:17 主跑、13:47 補跑，
GitHub 排程為 best-effort，實測延遲 5-6.5 小時，故排兩班互為備援）。
末端 `Verify live deployment` 比對線上資料日，不符時自動觸發 Pages 重建 → 空 commit → 仍失敗才亮紅燈。

**判斷「有沒有真的更新」要看 run log 的實際輸出**（找「跳過更新」字樣），
不能只看 run 的 conclusion——腳本跳過更新時也是 success。

## 防呆守則

- 資料日一律取自抓回資料的眾數，**絕不用系統時鐘**判斷交易日（排程延遲跨午夜會誤判）
- 單檔 ETF 抓取失敗 → 沿用前日快照並標 `stale`，不產生假異動、不中斷整批；全部失敗才 exit 1
- 持股權重合計超出 50–105% → 該檔判定為解析錯誤
- 單檔持股檔數對上次驟降 >50% → 中止（`--force` 可強制）
- 資料日未新於上次已處理日 → 跳過更新（log 明確印「跳過更新」）
