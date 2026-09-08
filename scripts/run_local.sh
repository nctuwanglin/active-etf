#!/usr/bin/env bash
# 本機手動更新的標準入口:先同步遠端(GitHub Actions 可能已推新 commit),
# 跑測試,再執行更新腳本。直接跑 update_dashboard.py 容易與 Actions 產生分岔。
# 用法:scripts/run_local.sh [--force]
set -euo pipefail
cd "$(dirname "$0")/.."

# 挑一個「真的裝了 requests」的直譯器。裸用 python3 不可靠:機器上可能同時有
# 系統 python 與 mise/pyenv 裝的版本,PATH 先抓到哪個會隨 shell 環境改變,
# 抓到沒有 requests 的那個時,錯誤會變成一長串 import 失敗而不是一句話講清楚。
# 要指定可自行帶入:PYTHON=/path/to/python scripts/run_local.sh
pick_python() {
  local candidates=("${PYTHON:-}" python3 /usr/bin/python3 python)
  for p in "${candidates[@]}"; do
    [ -n "$p" ] || continue
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import requests' >/dev/null 2>&1; then
      command -v "$p"
      return 0
    fi
  done
  return 1
}

if ! PY="$(pick_python)"; then
  echo "找不到裝有 requests 的 python。請先安裝:" >&2
  echo "    python3 -m pip install -r requirements.txt" >&2
  echo "或指定直譯器:PYTHON=/path/to/python scripts/run_local.sh" >&2
  exit 1
fi
echo "== 使用 $PY ($("$PY" -V 2>&1)) =="

echo "== git pull --rebase =="
git pull --rebase

echo "== 測試 =="
"$PY" -m unittest discover -s tests -q

echo "== 更新腳本 =="
"$PY" scripts/update_dashboard.py "$@"

echo "== 工作區狀態(如有變更請自行 commit/push)=="
git status -sb
