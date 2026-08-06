# -*- coding: utf-8 -*-
"""產生 index.html(自包含:資料內嵌、無外部依賴)。

版面沿用 twse-disposition 深色系與站內慣例:綠=加碼/新增,紅=減碼/剔除。
"""
import json

CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Inter','Noto Sans TC',sans-serif;font-feature-settings:"tnum" 1}
:root{--bg:#0a0e17;--panel:#111827;--panel-2:#1a2233;--line:#1f2937;
  --ink:#e5e7eb;--ink-dim:#94a3b8;--ink-mute:#64748b;
  --green:#10b981;--green-dim:#34d399;--red:#ef4444;--red-dim:#f87171;
  --amber:#f59e0b;--blue:#3b82f6}
a{color:inherit}
.mono{font-family:'JetBrains Mono','SF Mono',ui-monospace,monospace}
.wrap{max-width:78rem;margin:0 auto;padding:0 1rem}
header{border-bottom:1px solid var(--line);padding:1.25rem 0 1rem;
  background:linear-gradient(180deg,rgba(59,130,246,.06),transparent)}
h1{margin:0;font-size:1.3rem;letter-spacing:.02em}
.sub{color:var(--ink-dim);font-size:.8rem;margin-top:.35rem}
/* 固定 4 欄:auto-fit 在中等寬度會排成 3+1 落單 */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;margin:1rem 0}
@media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:.7rem .85rem}
.kpi .n{font-size:1.35rem;font-weight:700}
.kpi .l{color:var(--ink-mute);font-size:.7rem;letter-spacing:.06em;text-transform:uppercase}
nav{display:flex;gap:.4rem;margin:1rem 0;border-bottom:1px solid var(--line);flex-wrap:wrap}
nav button{background:none;border:none;color:var(--ink-dim);padding:.6rem .9rem;
  font:inherit;font-size:.9rem;cursor:pointer;border-bottom:2px solid transparent}
nav button.on{color:var(--ink);border-bottom-color:var(--blue);font-weight:600}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:1rem;margin-bottom:1rem}
.panel h2{margin:0 0 .75rem;font-size:.95rem;letter-spacing:.02em}
.panel h2 .hint{color:var(--ink-mute);font-size:.72rem;font-weight:400;margin-left:.5rem}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{text-align:left;color:var(--ink-mute);font-weight:600;font-size:.72rem;
  letter-spacing:.05em;padding:.4rem .5rem;border-bottom:1px solid var(--line);
  white-space:nowrap}
td{padding:.42rem .5rem;border-bottom:1px solid rgba(31,41,55,.5);white-space:nowrap}
tr:hover td{background:rgba(148,163,184,.04)}
.num{text-align:right}
.up{color:var(--green-dim)}.down{color:var(--red-dim)}
.pill{display:inline-flex;align-items:center;padding:1px 7px;font-size:.68rem;
  font-weight:600;border-radius:3px;letter-spacing:.03em}
.p-add{background:rgba(16,185,129,.16);color:#6ee7b7;border:1px solid rgba(16,185,129,.35)}
.p-inc{background:rgba(16,185,129,.10);color:#34d399;border:1px solid rgba(16,185,129,.25)}
.p-rem{background:rgba(239,68,68,.16);color:#fca5a5;border:1px solid rgba(239,68,68,.35)}
.p-dec{background:rgba(239,68,68,.10);color:#f87171;border:1px solid rgba(239,68,68,.25)}
.p-dispo{background:rgba(239,68,68,.2);color:#fca5a5;border:1px solid rgba(239,68,68,.4)}
.p-stale{background:rgba(245,158,11,.14);color:#fcd34d;border:1px solid rgba(245,158,11,.3)}
.p-gray{background:rgba(148,163,184,.1);color:#cbd5e1;border:1px solid rgba(148,163,184,.2)}
.controls{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-bottom:.85rem}
input,select{background:var(--panel-2);border:1px solid var(--line);color:var(--ink);
  border-radius:5px;padding:.4rem .6rem;font:inherit;font-size:.83rem}
input:focus,select:focus{outline:none;border-color:var(--blue)}
.chip{background:var(--panel-2);border:1px solid var(--line);color:var(--ink-dim);
  border-radius:99px;padding:.25rem .75rem;font-size:.76rem;cursor:pointer}
.chip.on{background:rgba(59,130,246,.16);border-color:rgba(59,130,246,.45);color:#bfdbfe}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:.85rem}
.etf-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:.9rem}
.etf-card h3{margin:0 0 .15rem;font-size:.92rem}
.etf-meta{display:grid;grid-template-columns:repeat(2,1fr);gap:.3rem .8rem;
  margin:.6rem 0;font-size:.76rem;color:var(--ink-dim)}
.etf-meta b{color:var(--ink);font-weight:600}
.bar-row{display:flex;align-items:center;gap:.5rem;margin:.22rem 0;font-size:.76rem}
.bar-row .nm{width:5.5rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{flex:1;height:9px;background:var(--panel-2);border-radius:2px;overflow:hidden}
/* span 預設 display:inline,寬高與背景都不會生效,必須 block */
.bar-fill{display:block;height:100%;background:linear-gradient(90deg,var(--blue),#60a5fa)}
.bar-row .pc{width:3.2rem;text-align:right;color:var(--ink-dim)}
details summary{cursor:pointer;color:var(--ink-dim);font-size:.78rem;margin-top:.6rem}
.empty{color:var(--ink-mute);font-size:.83rem;padding:1rem 0;text-align:center}
.note{color:var(--ink-mute);font-size:.74rem;line-height:1.6}
footer{border-top:1px solid var(--line);margin-top:2rem;padding:1rem 0 2rem;
  color:var(--ink-mute);font-size:.74rem;line-height:1.7}
.scroll{overflow-x:auto}
@media(max-width:640px){.etf-grid{grid-template-columns:1fr}}
"""

JS = r"""
const $ = s => document.querySelector(s);
const fmt = n => n == null ? '—' : n.toLocaleString('en-US');
const pct = n => n == null ? '—' : n.toFixed(2) + '%';
const money = n => n == null ? '—' : (n >= 1e8 ? (n/1e8).toFixed(1)+' 億'
  : n >= 1e4 ? (n/1e4).toFixed(0)+' 萬' : fmt(n));
const TYPE = {ADD:['新增','p-add'],INCREASE:['加碼','p-inc'],
              REMOVE:['剔除','p-rem'],DECREASE:['減碼','p-dec']};
const etfName = c => (DATA.etfs[c] || {}).name || c;
const dispoSet = new Set(DATA.crosslinks.dispo || []);
const notes = DATA.crosslinks.notes || {};

function stockCell(code, name) {
  let h = '<span class="mono">' + code + '</span> ' + (name || '');
  if (dispoSet.has(code)) h += ' <span class="pill p-dispo">處置</span>';
  if (notes[code]) h += ' <a href="' + notes[code] + '" target="_blank" title="研究筆記">📝</a>';
  return h;
}

/* ---------- Tab 1:今日異動 ---------- */
const allEvents = [];
for (const [etf, e] of Object.entries(DATA.etfs))
  for (const ev of e.events || []) allEvents.push({etf, ...ev});

let filterTypes = new Set(), filterEtf = '', filterQ = '';

function renderConsensus() {
  const c = DATA.consensus;
  const rows = [...c.increase.map(x => ({...x, dir: 'inc'})),
                ...c.decrease.map(x => ({...x, dir: 'dec'}))]
    .sort((a, b) => b.etfs.length - a.etfs.length);
  if (!rows.length) return '<div class="empty">今日沒有 2 檔以上 ETF 同步進出的標的</div>';
  return '<div class="scroll"><table><thead><tr><th>個股</th><th>方向</th>' +
    '<th class="num">檔數</th><th>ETF</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td>' + stockCell(r.code, r.name) + '</td>' +
      '<td><span class="pill ' + (r.dir === 'inc' ? 'p-inc">同步加碼' : 'p-dec">同步減碼') +
      '</span></td><td class="num ' + (r.dir === 'inc' ? 'up' : 'down') + '">' +
      r.etfs.length + '</td><td style="white-space:normal">' +
      r.etfs.map(e => '<span class="mono">' + e + '</span> ' + etfName(e)).join('、') +
      '</td></tr>').join('') + '</tbody></table></div>';
}

function renderEvents() {
  let rows = allEvents.filter(e =>
    (!filterTypes.size || filterTypes.has(e.type)) &&
    (!filterEtf || e.etf === filterEtf) &&
    (!filterQ || e.code.includes(filterQ) || (e.name || '').includes(filterQ)));
  if (!rows.length) return '<div class="empty">沒有符合條件的異動</div>';
  const order = {ADD: 0, INCREASE: 1, DECREASE: 2, REMOVE: 3};
  rows.sort((a, b) => order[a.type] - order[b.type] ||
    Math.abs(b.weight_delta || b.weight || 0) - Math.abs(a.weight_delta || a.weight || 0));
  return '<div class="scroll"><table><thead><tr><th>ETF</th><th>個股</th><th>異動</th>' +
    '<th class="num">權重</th><th class="num">權重變化</th><th class="num">股數變化</th>' +
    '</tr></thead><tbody>' + rows.map(e => {
      const [label, cls] = TYPE[e.type];
      const dw = e.weight_delta, ds = e.shares_delta_pct;
      const dir = (e.type === 'ADD' || e.type === 'INCREASE') ? 'up' : 'down';
      return '<tr><td><span class="mono">' + e.etf + '</span> <span style="color:var(--ink-dim)">' +
        etfName(e.etf) + '</span></td><td>' + stockCell(e.code, e.name) + '</td>' +
        '<td><span class="pill ' + cls + '">' + label + '</span></td>' +
        '<td class="num mono">' + (e.weight != null ? pct(e.weight) : pct(e.prev_weight)) + '</td>' +
        '<td class="num mono ' + dir + '">' + (dw != null ? (dw > 0 ? '+' : '') + dw.toFixed(2) : '—') + '</td>' +
        '<td class="num mono ' + dir + '">' + (ds != null ? (ds > 0 ? '+' : '') + ds.toFixed(1) + '%' : '—') + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}

function paintTab1() {
  $('#consensus').innerHTML = renderConsensus();
  $('#events').innerHTML = renderEvents();
}

/* ---------- Tab 2:各檔 ETF ---------- */
function etfCard(code, e) {
  const top = [...e.holdings].sort((a, b) => b.weight - a.weight).slice(0, 10);
  const max = top.length ? top[0].weight : 1;
  const bars = top.map(h => '<div class="bar-row"><span class="nm">' + h.name + '</span>' +
    '<span class="bar-track"><span class="bar-fill" style="width:' +
    (h.weight / max * 100).toFixed(1) + '%"></span></span>' +
    '<span class="pc mono">' + h.weight.toFixed(2) + '%</span></div>').join('');
  const stale = e.status === 'stale'
    ? ' <span class="pill p-stale">資料未更新</span>' : '';
  const prem = e.premium_pct;
  const full = '<details><summary>完整持股 ' + e.holdings.length + ' 檔</summary>' +
    '<div class="scroll"><table><thead><tr><th>個股</th><th class="num">股數</th>' +
    '<th class="num">權重</th></tr></thead><tbody>' +
    [...e.holdings].sort((a, b) => b.weight - a.weight).map(h =>
      '<tr><td>' + stockCell(h.code, h.name) + '</td><td class="num mono">' + fmt(h.shares) +
      '</td><td class="num mono">' + h.weight.toFixed(2) + '%</td></tr>').join('') +
    '</tbody></table></div></details>';
  return '<div class="etf-card"><h3><span class="mono">' + code + '</span> ' + e.name + stale + '</h3>' +
    '<div class="sub" style="font-size:.72rem">' + (e.issuer || '') + '投信 · 資料日 ' +
    (e.data_date || '—') + '</div>' +
    '<div class="etf-meta"><span>規模 <b>' + money(e.scale) + '</b></span>' +
    '<span>受益人 <b>' + fmt(e.holders) + '</b></span>' +
    '<span>淨值 <b>' + (e.nav != null ? e.nav.toFixed(2) : '—') + '</b></span>' +
    '<span>折溢價 <b class="' + (prem > 0 ? 'up' : prem < 0 ? 'down' : '') + '">' +
    (prem != null ? (prem > 0 ? '+' : '') + prem.toFixed(2) + '%' : '—') + '</b></span></div>' +
    bars + full + '</div>';
}

function paintTab2() {
  const active = Object.entries(DATA.etfs).filter(([, e]) => e.holdings.length);
  const pending = Object.entries(DATA.etfs).filter(([, e]) => !e.holdings.length);
  active.sort((a, b) => (b[1].scale || 0) - (a[1].scale || 0));
  let h = '<div class="etf-grid">' + active.map(([c, e]) => etfCard(c, e)).join('') + '</div>';
  if (pending.length)
    h += '<div class="panel" style="margin-top:1rem"><h2>已偵測、adapter 待補' +
      '<span class="hint">新掛牌或尚未支援的投信,補上 adapter 後自動納入</span></h2>' +
      pending.map(([c, e]) => '<span class="pill p-gray" style="margin:.2rem">' +
        c + ' ' + e.name + '</span>').join('') + '</div>';
  $('#etfs').innerHTML = h;
}

/* ---------- Tab 3:個股反查 ---------- */
function paintRanking() {
  const rows = Object.entries(DATA.stocks)
    .filter(([, s]) => s.etfs.length)
    .sort((a, b) => b[1].etfs.length - a[1].etfs.length ||
                    b[1].total_weight - a[1].total_weight).slice(0, 30);
  $('#ranking').innerHTML = '<div class="scroll"><table><thead><tr><th>#</th><th>個股</th>' +
    '<th class="num">持有檔數</th><th class="num">合計權重</th><th>ETF</th></tr></thead><tbody>' +
    rows.map(([code, s], i) => '<tr><td class="mono" style="color:var(--ink-mute)">' + (i + 1) +
      '</td><td>' + stockCell(code, s.name) + '</td>' +
      '<td class="num mono">' + s.etfs.length + '</td>' +
      '<td class="num mono">' + s.total_weight.toFixed(2) + '%</td>' +
      '<td style="white-space:normal;color:var(--ink-dim);font-size:.76rem">' +
      s.etfs.map(x => x.etf).join('、') + '</td></tr>').join('') + '</tbody></table></div>';
}

function lookup(q) {
  q = (q || '').trim();
  if (!q) { $('#lookup').innerHTML = '<div class="empty">輸入股票代號或名稱查詢</div>'; return; }
  const hit = Object.entries(DATA.stocks).find(([c, s]) =>
    c === q || c.includes(q) || (s.name || '').includes(q));
  if (!hit) { $('#lookup').innerHTML = '<div class="empty">「' + q +
    '」目前未被任何主動式 ETF 持有</div>'; return; }
  const [code, s] = hit;
  const rows = [...s.etfs].sort((a, b) => b.weight - a.weight);
  const evs = s.recent_events || [];
  $('#lookup').innerHTML = '<h2 style="margin:.2rem 0 .8rem">' + stockCell(code, s.name) +
    ' <span class="hint" style="color:var(--ink-mute);font-size:.76rem">被 ' + rows.length +
    ' 檔持有 · 合計權重 ' + s.total_weight.toFixed(2) + '%</span></h2>' +
    '<div class="scroll"><table><thead><tr><th>ETF</th><th class="num">權重</th>' +
    '<th class="num">股數</th><th>近期異動</th></tr></thead><tbody>' +
    rows.map(r => {
      const ev = evs.find(e => e.etf === r.etf);
      const tag = ev ? '<span class="pill ' + TYPE[ev.type][1] + '">' + TYPE[ev.type][0] +
        '</span> <span style="color:var(--ink-mute);font-size:.72rem">' + ev.date + '</span>' : '—';
      return '<tr><td><span class="mono">' + r.etf + '</span> ' + etfName(r.etf) + '</td>' +
        '<td class="num mono">' + r.weight.toFixed(2) + '%</td>' +
        '<td class="num mono">' + fmt(r.shares) + '</td><td>' + tag + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}

/* ---------- 初始化 ---------- */
function tab(n) {
  document.querySelectorAll('nav button').forEach((b, i) =>
    b.classList.toggle('on', i === n));
  document.querySelectorAll('section').forEach((s, i) =>
    s.style.display = i === n ? '' : 'none');
}
document.querySelectorAll('nav button').forEach((b, i) =>
  b.onclick = () => tab(i));
document.querySelectorAll('#typeChips .chip').forEach(c => c.onclick = () => {
  const t = c.dataset.t;
  if (filterTypes.has(t)) filterTypes.delete(t); else filterTypes.add(t);
  c.classList.toggle('on');
  $('#events').innerHTML = renderEvents();
});
$('#etfSel').onchange = e => { filterEtf = e.target.value; $('#events').innerHTML = renderEvents(); };
$('#evQ').oninput = e => { filterQ = e.target.value.trim(); $('#events').innerHTML = renderEvents(); };
$('#lookupQ').oninput = e => lookup(e.target.value);
paintTab1(); paintTab2(); paintRanking(); lookup(''); tab(0);
"""


def render(active, registry):
    date = active["updated"]
    etfs = active["etfs"]
    tracked = {c: e for c, e in etfs.items() if e["holdings"]}
    n_events = sum(len(e["events"]) for e in etfs.values())
    n_cons = len(active["consensus"]["increase"]) + len(active["consensus"]["decrease"])
    stale = [c for c, e in etfs.items() if e["status"] == "stale"]

    opts = "".join('<option value="{}">{} {}</option>'.format(c, c, e["name"])
                   for c, e in sorted(tracked.items()))
    chips = "".join(
        '<span class="chip" data-t="{}">{}</span>'.format(t, label)
        for t, label in (("ADD", "新增"), ("INCREASE", "加碼"),
                         ("DECREASE", "減碼"), ("REMOVE", "剔除")))
    stale_note = ('<div class="note" style="margin-top:.5rem">⚠️ '
                  + "、".join(stale) + " 今日抓取失敗,顯示前一日持股(不列入異動計算)。</div>"
                  ) if stale else ""

    return """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>台股主動式ETF追蹤 | Updated {date}</title>
<!-- AUTO:DATE:{date} -->
<style>{css}</style>
</head>
<body>
<header><div class="wrap">
  <h1>台股主動式 ETF 每日追蹤</h1>
  <div class="sub">經理人持股異動 · 持股比例分佈 · 個股反向查詢 　|　 資料日 <b>{date}</b></div>
</div></header>

<div class="wrap">
  <div class="kpis">
    <div class="kpi"><div class="n">{n_etf}</div><div class="l">追蹤 ETF</div></div>
    <div class="kpi"><div class="n">{n_stock}</div><div class="l">涵蓋個股</div></div>
    <div class="kpi"><div class="n">{n_events}</div><div class="l">今日異動</div></div>
    <div class="kpi"><div class="n">{n_cons}</div><div class="l">共識進出</div></div>
  </div>
  {stale_note}

  <nav>
    <button class="on">今日異動</button>
    <button>各檔 ETF</button>
    <button>個股反查</button>
  </nav>

  <section>
    <div class="panel">
      <h2>經理人共識榜<span class="hint">2 檔以上主動式 ETF 今日同方向調整的標的</span></h2>
      <div id="consensus"></div>
    </div>
    <div class="panel">
      <h2>今日持股異動明細</h2>
      <div class="controls">
        <span id="typeChips">{chips}</span>
        <select id="etfSel"><option value="">全部 ETF</option>{opts}</select>
        <input id="evQ" placeholder="搜尋個股代號/名稱" size="16">
      </div>
      <div id="events"></div>
      <div class="note" style="margin-top:.7rem">
        加碼/減碼已扣除申購贖回造成的等比例增減(以全體持股股數變化中位數校正),
        只呈現經理人的主動調整;門檻為校正後股數變化 ≥5% 且權重變化 ≥0.1 個百分點。
      </div>
    </div>
  </section>

  <section style="display:none">
    <div id="etfs"></div>
  </section>

  <section style="display:none">
    <div class="panel">
      <h2>個股反向查詢<span class="hint">查某檔股票被哪些主動式 ETF 持有、各佔多少</span></h2>
      <div class="controls"><input id="lookupQ" placeholder="輸入股票代號或名稱,如 2330 或 台積電" size="30"></div>
      <div id="lookup"></div>
    </div>
    <div class="panel">
      <h2>共識持股排行<span class="hint">被最多檔主動式 ETF 同時持有的個股 Top 30</span></h2>
      <div id="ranking"></div>
    </div>
  </section>

  <footer>
    資料來源:各投信官網每日公告之申購買回清單(PCF)/基金資產明細,收盤價取自 TWSE / TPEx。
    本頁每交易日盤後自動更新,僅供研究參考,不構成投資建議。<br>
    相關儀表板:<a href="https://nctuwanglin.github.io/twse-disposition/">台股處置股</a> ·
    <a href="https://nctuwanglin.github.io/stock-research-notes/">個股研究筆記</a> ·
    下游可讀 <a href="./active.json">active.json</a>
  </footer>
</div>
<script>const DATA = {data};</script>
<script>{js}</script>
</body>
</html>
""".format(date=date, css=CSS, js=JS, chips=chips, opts=opts,
           stale_note=stale_note,
           n_etf=len(tracked), n_stock=len(active["stocks"]),
           n_events=n_events, n_cons=n_cons,
           data=json.dumps(active, ensure_ascii=False, sort_keys=True))
