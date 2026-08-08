# -*- coding: utf-8 -*-
"""產生 index.html(自包含:資料內嵌、無外部依賴)。

深色版面,站內慣例綠漲紅跌(綠=加碼/新增,紅=減碼/剔除)。
配色不是憑感覺挑的,每個顏色都跑過 dataviz 的六項檢查(OKLab ΔE、Machado CVD
模擬、WCAG 對比,基準面板色 #111827);詳細理由寫在 CSS 內的註解。三個重點色
(藍/琥珀/洋紅)負責結構、活動、訊號三種角色,漲跌綠紅只用於狀態,兩組不混用。
"""
import json

# 篩選 chip 的字符,與 JS 端 TYPE 表一致(綠↔紅對紅綠色盲不可靠,方向一律配字符)
GLYPH = {"ADD": "✚", "INCREASE": "▲", "DECREASE": "▼", "REMOVE": "✕"}

# counterapi.dev 的命名空間,沿用 credit-card-guide 的做法(免帳號、純前端)
COUNTER_NS = "wanglin-active-etf-2026"

CSS = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:'Inter','Noto Sans TC',sans-serif;font-feature-settings:"tnum" 1}
/* 配色以 dataviz 六項檢查實算過(OKLab ΔE、Machado CVD 模擬、WCAG 對比),
   面板色 #111827 為基準,不是憑眼睛挑的:
   - 三個重點色 blue/amber/magenta 全對(all-pairs CVD ΔE 13.2、常色視覺 19.3)
   - 藍色 sequential ramp 只用對比 >=3:1 的 100-500 階(550 以下在深色面板看不見)
   - 綠↔紅 deutan ΔE 僅 6.5(紅綠色盲的典型弱點),故四種異動 pill 一律配
     ▲▼✚✕ 字符 + 文字,色相絕不單獨承載方向 */
:root{--bg:#080b12;--panel:#111827;--panel-2:#1a2233;--line:#243044;
  --ink:#e8ebf0;--ink-dim:#9aa8bd;--ink-mute:#6b7a91;
  /* 狀態色:綠漲紅跌(站內慣例) */
  --up:#34d399;--up-deep:#059669;--down:#f87171;--down-deep:#dc2626;
  /* 三個重點色 */
  --blue:#3987e5;--blue-lt:#7cb2f0;--amber:#fab219;--magenta:#e879a8;
  /* 權重 bar 的 sequential 藍階(低→高) */
  --seq-lo:#256abf;--seq-hi:#9ec5f4}
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
/* 每塊各自的重點色只上在頂條與數字;標籤文字一律用 ink token 不染色。
   四塊的識別靠文字標籤,顏色是強調不是識別通道——所以不受類別色 CVD 門檻約束,
   但仍只用實算通過的三個重點色(藍/琥珀/洋紅),避免與漲跌綠紅混淆。 */
.kpi{position:relative;background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:.8rem .9rem .75rem;overflow:hidden}
.kpi::before{content:'';position:absolute;inset:0 0 auto 0;height:3px;
  background:var(--accent,var(--blue))}
.kpi .n{font-size:1.5rem;font-weight:700;color:var(--accent,var(--ink));
  line-height:1.15;letter-spacing:-.01em}
.kpi .l{color:var(--ink-dim);font-size:.71rem;letter-spacing:.06em;margin-top:.1rem}
.k-etf{--accent:var(--blue)}
.k-stock{--accent:var(--blue-lt)}
.k-move{--accent:var(--amber)}
.k-cons{--accent:var(--magenta)}
/* 今日無異動時不該用亮色喊「0」——沒事發生就該安靜下來 */
.kpi.zero .n{color:var(--ink-mute)}
.kpi.zero::before{background:var(--line)}
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
.up{color:var(--up)}.down{color:var(--down)}
.pill{display:inline-flex;align-items:center;gap:3px;padding:1.5px 7px;font-size:.69rem;
  font-weight:600;border-radius:4px;letter-spacing:.03em;white-space:nowrap}
.pill .g{font-size:.62rem;line-height:1}
/* 方向用色相(綠漲紅跌)、強度用實心/淡底:進出場實心,加減碼淡底。
   色相對紅綠色盲不可靠,所以 ▲▼✚✕ 字符是必要的第二通道,不是裝飾。 */
.p-add{background:var(--up-deep);color:#eafff6;border:1px solid var(--up)}
.p-inc{background:rgba(52,211,153,.13);color:var(--up);border:1px solid rgba(52,211,153,.4)}
.p-rem{background:var(--down-deep);color:#fff1f1;border:1px solid var(--down)}
.p-dec{background:rgba(248,113,113,.13);color:var(--down);border:1px solid rgba(248,113,113,.4)}
.p-dispo{background:rgba(250,178,25,.15);color:var(--amber);border:1px solid rgba(250,178,25,.45)}
.p-stale{background:rgba(250,178,25,.12);color:var(--amber);border:1px solid rgba(250,178,25,.3)}
.p-note{background:rgba(57,135,229,.14);color:var(--blue-lt);border:1px solid rgba(57,135,229,.4)}
.p-gray{background:rgba(154,168,189,.1);color:var(--ink-dim);border:1px solid rgba(154,168,189,.22)}
.controls{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin-bottom:.85rem}
input,select{background:var(--panel-2);border:1px solid var(--line);color:var(--ink);
  border-radius:5px;padding:.4rem .7rem;font:inherit;font-size:.83rem}
/* 中文 placeholder 用 size 屬性算出來的寬度會不夠(size 以英數字寬為準),
   一律改用 min-width,否則「搜尋個股代號/名稱」會貼齊邊框甚至被裁掉。 */
#evQ{min-width:13rem}
#lookupQ{min-width:22rem}
@media(max-width:640px){#evQ,#lookupQ{min-width:100%}}
input:focus,select:focus{outline:none;border-color:var(--blue)}
/* 篩選 chip 是「單選」:點另一個就換過去,再點同一個取消回到全部。
   選取態要一眼看得出來,故未選為描邊、選取為實心底色,並各自帶事件類型的顏色
   (新增/加碼綠、減碼/剔除紅),與異動 pill 同一套視覺語言。 */
.chip{background:transparent;border:1px solid var(--line);color:var(--ink-dim);
  border-radius:99px;padding:.28rem .8rem;font-size:.76rem;cursor:pointer;
  display:inline-flex;align-items:center;gap:4px;user-select:none;
  transition:background .12s,color .12s,border-color .12s}
.chip .g{font-size:.62rem;line-height:1}
.chip:hover{border-color:var(--c,var(--blue));color:var(--ink)}
.chip.on{background:var(--c,var(--blue));border-color:var(--c,var(--blue));
  color:#0a0e17;font-weight:700}
.chip[data-t="ADD"],.chip[data-t="INCREASE"]{--c:var(--up)}
.chip[data-t="REMOVE"],.chip[data-t="DECREASE"]{--c:var(--down)}
.chip-hint{color:var(--ink-mute);font-size:.72rem;margin-left:.15rem}
.etf-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:.85rem}
.etf-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:.9rem}
.etf-card h3{margin:0 0 .15rem;font-size:.92rem}
.etf-meta{display:grid;grid-template-columns:repeat(2,1fr);gap:.3rem .8rem;
  margin:.6rem 0;font-size:.76rem;color:var(--ink-dim)}
.etf-meta b{color:var(--ink);font-weight:600}
.bar-row{display:flex;align-items:center;gap:.5rem;margin:.22rem 0;font-size:.76rem}
.bar-row .nm{width:5.5rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{flex:1;height:10px;background:rgba(154,168,189,.09);border-radius:2px;
  overflow:hidden;position:relative}
/* span 預設 display:inline,寬高與背景都不會生效,必須 block。
   顏色是 sequential(權重越大越亮),不是按名次配色——名次配色會讓同一檔股票
   在不同 ETF 卡片上換色。資料端末圓角 4px 是 dataviz 的 mark spec。 */
.bar-fill{display:block;height:100%;border-radius:0 4px 4px 0;
  background:var(--c,var(--blue))}
/* 今日有異動的持股,在 bar 末端加一道方向色記號(色相+位置雙通道) */
.bar-row.moved .bar-track::after{content:'';position:absolute;top:0;bottom:0;right:0;
  width:3px;background:var(--mv)}
.bar-row.up{--mv:var(--up)}.bar-row.down{--mv:var(--down)}
.bar-row .pc{width:3.2rem;text-align:right;color:var(--ink-dim)}
.bar-row.moved .pc{color:var(--mv);font-weight:600}
details summary{cursor:pointer;color:var(--ink-dim);font-size:.78rem;margin-top:.6rem}
.empty{color:var(--ink-mute);font-size:.83rem;padding:1rem 0;text-align:center}
.note{color:var(--ink-mute);font-size:.74rem;line-height:1.6}
footer{border-top:1px solid var(--line);margin-top:2rem;padding:1rem 0 2rem;
  color:var(--ink-mute);font-size:.74rem;line-height:1.7}
.visits{display:flex;justify-content:center;gap:1.2rem;margin-top:1rem;
  padding-top:.9rem;border-top:1px solid var(--line);
  font-family:'JetBrains Mono','SF Mono',ui-monospace,monospace;
  font-size:.72rem;color:var(--ink-mute)}
.visits b{color:var(--ink-dim);font-weight:700}
.scroll{overflow-x:auto}
@media(max-width:640px){.etf-grid{grid-template-columns:1fr}}

/* ---------- 手機版:.rt 的表格轉成卡片 ----------
   窄螢幕下橫向捲動的表格很難用:關鍵欄位(張數/金額)被推到畫面外,而且只要有
   一欄會換行(例如共識榜的 ETF 清單),整列就被撐得極高、中間全是空白。
   這裡把每一列改成一張卡片,欄位標籤取自 td 的 data-l,一份 HTML 兩種版型。 */
@media(max-width:640px){
  .rt{overflow-x:visible}
  .rt table,.rt tbody,.rt tr,.rt td{display:block;width:auto}
  .rt thead{display:none}
  .rt tr{border:1px solid var(--line);border-radius:8px;
    padding:.6rem .7rem;margin-bottom:.5rem;background:var(--panel-2)}
  .rt tr:hover td{background:none}
  .rt td{border:0;padding:.2rem 0;white-space:normal;text-align:left;
    display:flex;justify-content:space-between;align-items:center;gap:.9rem}
  .rt td::before{content:attr(data-l);color:var(--ink-mute);font-size:.72rem;
    flex:none}
  /* 第一欄(個股或 ETF)當卡片標題:不顯示標籤、獨佔一行 */
  .rt td:first-child{display:block;font-size:.92rem;font-weight:600;
    padding-bottom:.4rem;margin-bottom:.35rem;border-bottom:1px solid var(--line)}
  .rt td:first-child::before{content:none}
  .rt td.num.mono:not(:first-child){font-variant-numeric:tabular-nums}
  /* 值為「—」的欄位在卡片上只是雜訊(個股反查每張卡都會多一行空的近期異動) */
  .rt td.na{display:none}
  /* ETF 清單是多個 span + 頓號,在 flex + space-between 下每個都成了獨立項目,
     會被平均拉開。改成標籤獨立一行、代號在下方自然靠左排。 */
  .rt td.etflist{display:block}
  .rt td.etflist::before{display:block;margin-bottom:.25rem}
}
"""

JS = r"""
const $ = s => document.querySelector(s);
const fmt = n => n == null ? '—' : n.toLocaleString('en-US');
const pct = n => n == null ? '—' : n.toFixed(2) + '%';
const money = n => n == null ? '—' : (n >= 1e8 ? (n/1e8).toFixed(1)+' 億'
  : n >= 1e4 ? (n/1e4).toFixed(0)+' 萬' : fmt(n));
// 買賣金額/張數一律帶正負號。money() 收的是絕對值,負號由這裡補,
// 否則減碼會顯示成「1.9 億」看起來像買進。
const signed = (text, v) => (v > 0 ? '+' : v < 0 ? '−' : '') + String(text).replace(/^-/, '');
// [文字, class, 字符]。字符不是裝飾:綠↔紅在紅綠色盲下 deutan ΔE 只有 6.5,
// 方向必須有色相以外的第二通道才讀得出來。
const TYPE = {ADD:['新增','p-add','✚'],INCREASE:['加碼','p-inc','▲'],
              REMOVE:['剔除','p-rem','✕'],DECREASE:['減碼','p-dec','▼']};
const pill = t => '<span class="pill ' + TYPE[t][1] + '"><span class="g">'
  + TYPE[t][2] + '</span>' + TYPE[t][0] + '</span>';
// 權重 → sequential 藍階(低→高越亮)。只走對比 >=3:1 的區段,深色面板才看得見。
const SEQ_LO = [37,106,191], SEQ_HI = [158,197,244];
const seqColor = (w, max) => {
  const t = max > 0 ? Math.min(1, Math.max(0, w / max)) : 0;
  const c = SEQ_LO.map((lo, i) => Math.round(lo + (SEQ_HI[i] - lo) * t));
  return 'rgb(' + c.join(',') + ')';
};
const dispoSet = new Set(DATA.crosslinks.dispo || []);
const notes = DATA.crosslinks.notes || {};

function stockCell(code, name) {
  let h = '<span class="mono">' + code + '</span> ' + (name || '');
  if (dispoSet.has(code)) h += ' <span class="pill p-dispo"><span class="g">!</span>處置</span>';
  if (notes[code]) h += ' <a href="' + notes[code] + '" target="_blank" title="研究筆記"'
    + ' class="pill p-note" style="text-decoration:none"><span class="g">◆</span>筆記</a>';
  return h;
}

/* ---------- Tab 1:今日異動 ---------- */
const allEvents = [];
for (const [etf, e] of Object.entries(DATA.etfs))
  for (const ev of e.events || []) allEvents.push({etf, ...ev});

let filterType = '', filterEtf = '', filterQ = '';  // filterType 空字串=全部(單選)

// 該檔今日的淨買賣金額(絕對值)。沒有收盤價就回 null,排序時排在最後。
function consAmount(r) {
  const px = (DATA.stocks[r.code] || {}).close;
  return (r.shares_delta != null && px) ? Math.abs(r.shares_delta * px) : null;
}

function renderConsensus() {
  const c = DATA.consensus;
  // 先分加碼/減碼兩組(加碼在前),組內再依金額由大到小
  const byAmount = (a, b) => {
    const x = consAmount(a), y = consAmount(b);
    if (x == null && y == null) return b.etfs.length - a.etfs.length;
    if (x == null) return 1;
    if (y == null) return -1;
    return y - x;
  };
  const rows = [...c.increase.map(x => ({...x, dir: 'inc'})).sort(byAmount),
                ...c.decrease.map(x => ({...x, dir: 'dec'})).sort(byAmount)];
  if (!rows.length) return '<div class="empty">今日沒有 2 檔以上 ETF 同步進出的標的</div>';
  return '<div class="scroll rt"><table><thead><tr><th>個股</th><th>方向</th>' +
    '<th class="num">檔數</th><th class="num">張數</th><th class="num">金額</th>' +
    '<th>ETF</th></tr></thead><tbody>' +
    rows.map(r => {
      const cls = r.dir === 'inc' ? 'up' : 'down';
      // shares_delta 是這幾檔 ETF 對該股的淨買賣股數,除以 1000 換算成張
      const lots = r.shares_delta == null ? null : r.shares_delta / 1000;
      const px = (DATA.stocks[r.code] || {}).close;
      const amt = (r.shares_delta != null && px) ? r.shares_delta * px : null;  // 帶正負號
      return '<tr><td data-l="個股">' + stockCell(r.code, r.name) + '</td>' +
      '<td data-l="方向"><span class="pill ' + (r.dir === 'inc'
        ? 'p-inc"><span class="g">▲</span>同步加碼' : 'p-dec"><span class="g">▼</span>同步減碼') +
      '</span></td><td data-l="檔數" class="num ' + cls + '">' + r.etfs.length + '</td>' +
      '<td data-l="張數" class="num mono ' + cls + '">' +
        (lots == null ? '—' : signed(Math.round(lots).toLocaleString('en-US'), lots)) +
      '</td><td data-l="金額" class="num mono ' + cls + '">' +
        (amt == null ? '—' : signed(money(Math.abs(amt)), amt)) +
      '</td><td data-l="ETF" class="etflist" style="white-space:normal">' +
      r.etfs.map(e => '<span class="mono">' + e + '</span>').join('、') +
      '</td></tr>';
    }).join('') + '</tbody></table></div>';
}

function renderEvents() {
  let rows = allEvents.filter(e =>
    (!filterType || e.type === filterType) &&
    (!filterEtf || e.etf === filterEtf) &&
    (!filterQ || e.code.includes(filterQ) || (e.name || '').includes(filterQ)));
  if (!rows.length) return '<div class="empty">沒有符合條件的異動</div>';
  const order = {ADD: 0, INCREASE: 1, DECREASE: 2, REMOVE: 3};
  rows.sort((a, b) => order[a.type] - order[b.type] ||
    Math.abs(b.weight_delta || b.weight || 0) - Math.abs(a.weight_delta || a.weight || 0));
  return '<div class="scroll rt"><table><thead><tr><th>ETF</th><th>個股</th><th>異動</th>' +
    '<th class="num">權重</th><th class="num">權重變化</th><th class="num">股數變化</th>' +
    '</tr></thead><tbody>' + rows.map(e => {
      const dw = e.weight_delta, ds = e.shares_delta_pct;
      const dir = (e.type === 'ADD' || e.type === 'INCREASE') ? 'up' : 'down';
      return '<tr><td data-l="ETF"><span class="mono">' + e.etf + '</span></td>' +
        '<td data-l="個股">' + stockCell(e.code, e.name) + '</td>' +
        '<td data-l="異動">' + pill(e.type) + '</td>' +
        '<td data-l="權重" class="num mono">' + (e.weight != null ? pct(e.weight) : pct(e.prev_weight)) + '</td>' +
        '<td data-l="權重變化" class="num mono ' + dir + (dw == null ? ' na' : '') + '">' +
          (dw != null ? (dw > 0 ? '+' : '') + dw.toFixed(2) : '—') + '</td>' +
        '<td data-l="股數變化" class="num mono ' + dir + (ds == null ? ' na' : '') + '">' +
          (ds != null ? (ds > 0 ? '+' : '') + ds.toFixed(1) + '%' : '—') + '</td></tr>';
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
  // 這檔 ETF 今日動過的標的:bar 末端加方向色記號,一眼看出經理人改了哪幾檔
  const moves = {};
  for (const ev of e.events || [])
    moves[ev.code] = (ev.type === 'ADD' || ev.type === 'INCREASE') ? 'up' : 'down';
  const bars = top.map(h => {
    const mv = moves[h.code];
    return '<div class="bar-row' + (mv ? ' moved ' + mv : '') + '">' +
      '<span class="nm">' + h.name + '</span>' +
      '<span class="bar-track"><span class="bar-fill" style="width:' +
      (h.weight / max * 100).toFixed(1) + '%;--c:' + seqColor(h.weight, max) + '"></span></span>' +
      '<span class="pc mono">' + h.weight.toFixed(2) + '%</span></div>';
  }).join('');
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
    '<div class="scroll rt"><table><thead><tr><th>ETF</th><th class="num">權重</th>' +
    '<th class="num">股數</th><th>近期異動</th></tr></thead><tbody>' +
    rows.map(r => {
      const ev = evs.find(e => e.etf === r.etf);
      const tag = ev ? pill(ev.type) +
        ' <span style="color:var(--ink-mute);font-size:.72rem">' + ev.date + '</span>' : '—';
      return '<tr><td data-l="ETF"><span class="mono">' + r.etf + '</span></td>' +
        '<td data-l="權重" class="num mono">' + r.weight.toFixed(2) + '%</td>' +
        '<td data-l="股數" class="num mono">' + fmt(r.shares) + '</td>' +
        '<td data-l="近期異動"' + (ev ? '' : ' class="na"') + '>' + tag + '</td></tr>';
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
// 單選:點另一個就換過去,再點同一個則取消回到「全部」
document.querySelectorAll('#typeChips .chip').forEach(c => c.onclick = () => {
  const t = c.dataset.t;
  filterType = (filterType === t) ? '' : t;
  document.querySelectorAll('#typeChips .chip').forEach(
    x => x.classList.toggle('on', x.dataset.t === filterType));
  $('#events').innerHTML = renderEvents();
});
$('#etfSel').onchange = e => { filterEtf = e.target.value; $('#events').innerHTML = renderEvents(); };
$('#evQ').oninput = e => { filterQ = e.target.value.trim(); $('#events').innerHTML = renderEvents(); };
$('#lookupQ').oninput = e => lookup(e.target.value);
paintTab1(); paintTab2(); paintRanking(); lookup(''); tab(0);

/* 瀏覽計數:counterapi.dev,免帳號、純前端,與信用卡儀表板同一套做法。
   /total/up 與 /day-YYYYMMDD/up 各遞增一次並回傳計數;抓不到就整塊不顯示,
   不要在頁尾留一行壞掉的字。 */
(function () {
  const base = 'https://api.counterapi.dev/v1/__NS__';
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const el = $('#visits');
  Promise.all([
    fetch(base + '/total/up').then(r => r.json()),
    fetch(base + '/day-' + today + '/up').then(r => r.json()),
  ]).then(([total, day]) => {
    el.innerHTML = '<span>今日瀏覽 <b>' + (day.count || 0).toLocaleString('en-US') +
      '</b></span><span>累計瀏覽 <b>' + (total.count || 0).toLocaleString('en-US') + '</b></span>';
  }).catch(() => { el.style.display = 'none'; });
})();
"""


def render(active, registry):
    date = active["updated"]
    etfs = active["etfs"]
    tracked = {c: e for c, e in etfs.items() if e["holdings"]}
    n_events = sum(len(e["events"]) for e in etfs.values())
    n_cons = len(active["consensus"]["increase"]) + len(active["consensus"]["decrease"])
    stale = [c for c, e in etfs.items() if e["status"] == "stale"]

    # 下拉也只顯示代號(使用者要求除「各檔 ETF」頁外都不出現中文名)
    opts = "".join('<option value="{0}">{0}</option>'.format(c)
                   for c in sorted(tracked))
    chips = "".join(
        '<span class="chip" data-t="{0}"><span class="g">{2}</span>{1}</span>'.format(
            t, label, GLYPH[t])
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
    <div class="kpi k-etf"><div class="n">{n_etf}</div><div class="l">追蹤 ETF</div></div>
    <div class="kpi k-stock"><div class="n">{n_stock}</div><div class="l">涵蓋個股</div></div>
    <div class="kpi k-move{z_events}"><div class="n">{n_events}</div><div class="l">今日異動</div></div>
    <div class="kpi k-cons{z_cons}"><div class="n">{n_cons}</div><div class="l">共識進出</div></div>
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
        <span id="typeChips">{chips}</span><span class="chip-hint">(點選篩選一種,再點一次看全部)</span>
        <select id="etfSel"><option value="">全部 ETF</option>{opts}</select>
        <input id="evQ" placeholder="搜尋個股代號 / 名稱">
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
      <div class="controls"><input id="lookupQ" placeholder="輸入股票代號或名稱,如 2330 或 台積電"></div>
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
    <a href="https://nctuwanglin.github.io/stock-research-notes/">個股研究筆記</a>
  </footer>
  <div class="visits" id="visits"></div>
</div>
<script>const DATA = {data};</script>
<script>{js}</script>
</body>
</html>
""".format(date=date, css=CSS, js=JS.replace("__NS__", COUNTER_NS),
           chips=chips, opts=opts,
           stale_note=stale_note,
           n_etf=len(tracked), n_stock=len(active["stocks"]),
           n_events=n_events, n_cons=n_cons,
           z_events="" if n_events else " zero", z_cons="" if n_cons else " zero",
           data=json.dumps(active, ensure_ascii=False, sort_keys=True))
