/* Unit-level DOM adapter, not a real-browser visual or layout test. No network. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||'index.html','utf8');
const elements=new Map(),groups={};
class Element {
  constructor(id=''){this.id=id;this.value='';this.hidden=false;this.style={};this.dataset={};this.listeners={};this.classList={toggle(){}};this._html='';}
  set innerHTML(s){this._html=s;for(const m of s.matchAll(/id="([^"]+)"/g))if(!elements.has(m[1]))elements.set(m[1],new Element(m[1]));}
  get innerHTML(){return this._html;}
  addEventListener(n,fn){this.listeners[n]=fn;}
  setAttribute(){}
  scrollIntoView(){}
  click(){if(this.onclick)this.onclick({target:this});}
}
for(const m of html.matchAll(/id="([^"]+)"/g))elements.set(m[1],new Element(m[1]));
groups['nav button']=Array.from({length:4},()=>new Element());
groups['section']=Array.from({length:4},()=>new Element());
groups['#typeChips .chip']=['ADD','INCREASE','DECREASE','REMOVE'].map(t=>{const e=new Element();e.dataset.t=t;return e;});
const doc={getElementById:id=>elements.get(id)||null,querySelector:s=>s.startsWith('#')?elements.get(s.slice(1))||null:null,
 querySelectorAll:s=>groups[s]||[],createElement:()=>new Element()};
const blobs=[],ctx={document:doc,console,Date,Set,Map,Blob,URL:{createObjectURL:b=>{blobs.push(b);return 'blob:test';},revokeObjectURL(){}},setTimeout:fn=>fn(),fetch:()=>Promise.reject(new Error('offline unit test'))};
ctx.window=ctx;ctx.globalThis=ctx;vm.createContext(ctx);
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
for(const s of scripts)vm.runInContext(s,ctx,{timeout:10000});
assert(elements.get('trendStockName').textContent.includes('2330'));
assert(elements.get('trendDaily').innerHTML.includes('<svg'));
for(const id of ['trendCumulative','trendHoldings']) {
  const dates=[...elements.get(id).innerHTML.matchAll(/data-day="([^"]+)"/g)].map(m=>m[1]);
  assert(dates.every(d=>ctx.TREND_DATA.windows['20'].dates.includes(d)), 'Only selectable trading periods should be interactive');
}
assert(elements.get('trendRankTable').innerHTML.includes('data-stock='));
elements.get('trendWindow').onchange({target:{value:'60'}});
assert.equal(elements.get('trendBody').hidden,true);
assert(elements.get('trendEmpty').textContent.includes('歷史不足'));
elements.get('trendWindow').onchange({target:{value:'5'}});
assert.equal(elements.get('trendBody').hidden,false);
ctx.ETFTrends.openStock('2454');
assert(elements.get('trendStockName').textContent.includes('2454'));
assert.equal(groups.section[2].style.display,'');
elements.get('trendDirection').onchange({target:{value:'sell'}});
assert(elements.get('trendRankTable').innerHTML.includes('data-stock='));
elements.get('trendExport').click();
assert.equal(blobs.length,1);
(async()=>{const csv=await blobs[0].text();assert(csv.includes('included_in_fixed_cohort'));assert(csv.includes('2454'));console.log('Dashboard initialization/controls/export smoke checks passed (unit DOM; no visual assertions).');})();
