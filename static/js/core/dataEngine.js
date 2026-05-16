export function processCommits(r) { return r.map(c=>{ const m=(c.s||"").match(/^([a-zA-Z_-]+)(?:\(([^)]+)\))?:\s*(.*)$/); if(m){c.t=m[1].toLowerCase();c.scope=m[2]||'global';c.clean_s=m[3];}else{c.t='chore';c.scope='global';c.clean_s=c.s;} return c; }); }
export function fmtCD(ts){ const d=new Date(ts*1000); const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]; return `${m[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}`; }
export function fmtTableDate(ts){ const d=new Date(ts*1000); const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]; return `${m[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}, '${String(d.getFullYear()).slice(-2)}`; }
export function fmtStr(ts){ const d=new Date(ts*1000); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
export function calcMAvg(arr, mode, cArr, isLin) {
    if(mode===0) return [];
    if(mode===1){ const w=5; return arr.map((_,i)=>{ const sl=arr.slice(Math.max(0,i-w+1),i+1); const a=sl.reduce((s,x)=>s+x,0)/sl.length; return isLin?{x:cArr[i].ts,y:parseFloat(a.toFixed(2))}:parseFloat(a.toFixed(2));}); }
    if(mode===2){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); return cArr.map(c=>isLin?{x:c.ts,y:mx[fmtStr(c.ts)]}:mx[fmtStr(c.ts)]); }
    if(mode===3){ let ds={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!ds[d])ds[d]=[]; ds[d].push(arr[i]); }); let md={}; Object.keys(ds).forEach(d=>{ const s=[...ds[d]].sort((a,b)=>a-b); const mid=Math.floor(s.length/2); md[d]=s.length%2!==0?s[mid]:(s[mid-1]+s[mid])/2; }); return cArr.map(c=>isLin?{x:c.ts,y:md[fmtStr(c.ts)]}:md[fmtStr(c.ts)]); }
    if(mode===4){ let dd={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!dd[d])dd[d]={s:0,c:0}; dd[d].s+=arr[i]; dd[d].c++; }); const dy=Object.keys(dd); return cArr.map((c,i)=>{ const d=fmtStr(c.ts); const ix=dy.indexOf(d); const sl=dy.slice(Math.max(0,ix-6),ix+1); let ts=0,tv=0; sl.forEach(dy=>{ts+=dd[dy].s;tv+=dd[dy].c;}); const a=tv>0?ts/tv:arr[i]; return isLin?{x:c.ts,y:parseFloat(a.toFixed(2))}:parseFloat(a.toFixed(2)); }); }
    if(mode===5){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); const dy=Object.keys(mx); return cArr.map(c=>{ const d=fmtStr(c.ts); const ix=dy.indexOf(d); const sl=dy.slice(Math.max(0,ix-6),ix+1); const hw=Math.max(...sl.map(dy=>mx[dy])); return isLin?{x:c.ts,y:hw}:hw; }); }
    return [];
}
export const getTop25 = (arr) => { const s=[...arr].sort((a,b)=>b-a); return s[Math.floor(s.length*0.25)] || 999; };
