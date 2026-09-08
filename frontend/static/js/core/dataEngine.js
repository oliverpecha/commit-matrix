export function extractDynamicAxes(commits) { if (!commits || !commits.length) return []; const ex = ['hash_long', 'hash_short', 'subject', 'author_date', 'lines_added', 'lines_deleted', 'n', 'h', 's', 'ts', 'tot', 'tier']; return Object.keys(commits[0]).filter(k => !ex.includes(k) && typeof commits[0][k] === 'number'); }
export function processCommits(r) {
    if (!r || !r.length) return [];
    const isCSV = Array.isArray(r[0]);
    const list = isCSV ? r.slice(1).map(row => {
        const obj = {};
        r[0].forEach((k, idx) => { obj[k] = row[idx]; });
        return obj;
    }) : r;

    return list.map((c, i) => {
        const lc = {};
        for (let k in c) {
            if (k.trim().length === 1) {
                lc[k.trim()] = c[k];
            } else {
                lc[k.trim().toLowerCase()] = c[k];
            }
        }

        const subj = c.s || c.subject || lc.subject || lc.clean_s || lc.message || "";
        const m = subj.match(/^([a-zA-Z_-]+)(?:\(([^)]+)\))?:\s*(.*)$/);
        
        if (m) { 
            c.t = m[1].toLowerCase(); 
            c.scope = m[2] || lc.scope || 'global'; 
            c.clean_s = m[3]; 
        } else { 
            c.t = lc.type || c.type || 'chore'; 
            c.scope = lc.scope || c.scope || 'global'; 
            c.clean_s = subj || 'chore: unknown'; 
        }
        c.s = subj;
        c.p_type = c.t;

        const toB = (v) => v === true || String(v).toLowerCase() === "true" || v === 1 || v === "1";
        c.t_metrics = toB(c.t_metrics ?? lc.metrics ?? lc.touches_metrics);
        c.t_preflight = toB(c.t_preflight ?? lc.preflight ?? lc.touches_preflight);
        c.t_tests = toB(c.t_tests ?? lc.tests ?? lc.touches_tests);
        c.t_docs = toB(c.t_docs ?? lc.docs ?? lc.touches_docs);
        c.t_dashboard = toB(c.t_dashboard ?? lc.dashboard ?? lc.touches_dashboard);
        c.t_config = toB(c.t_config ?? lc.config ?? lc.touches_config);
        c.t_scripts = toB(c.t_scripts ?? lc.scripts ?? lc.touches_scripts);
        c.t_proxy = toB(c.t_proxy ?? lc.proxy ?? lc.touches_proxy);
        c.t_core = toB(c.t_core ?? lc.critical ?? lc.core ?? lc.touches_core);

        c.tot = Number(c.tot ?? lc.total) || 0;
        c.C = Number(c.C ?? lc.c) || 0;
        c.I = Number(c.I ?? lc.i) || 0;
        c.R = Number(c.R ?? lc.r) || 0;
        c.S = Number(c.S ?? lc.s) || 0; 
        c.D = Number(c.D ?? lc.d) || 0;
        
        if (c.ts) {
            c.ts = Number(c.ts);
        } else if (lc.date) {
            c.ts = Math.floor(new Date(String(lc.date).replace("'", "20")).getTime() / 1000) || 0;
        } else {
            c.ts = 0;
        }

        c.n = Number(c.n ?? lc['#']) || (i + 1);
        c.lines_added = Number(c.lines_added ?? lc.additions) || 0;
        c.lines_deleted = Number(c.lines_deleted ?? lc.deletions) || 0;
        c.h = c.h || lc.hash || "";
          
        const rawTier = String(c.tier || lc.tier || "Routine").toLowerCase();
        if (rawTier === 'critical' || rawTier === 'pivotal') c.tier = 'Pivotal';
        else if (rawTier === 'significant' || rawTier === 'core') c.tier = 'Core';
        else c.tier = 'Minor';
          
        return c;
    });
}
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
