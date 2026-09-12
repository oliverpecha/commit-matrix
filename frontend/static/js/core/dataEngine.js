export function extractDynamicAxes(commits) { if (!commits || !commits.length) return []; const keys = new Set(); commits.forEach(c => Object.keys(c).forEach(k => { if (k.startsWith('touches_')) keys.add(k); })); return Array.from(keys).sort(); }
export function processCommits(r) {
    if (!r || !r.length) return [];
    const isCSV = Array.isArray(r[0]);
    const list = isCSV ? r.slice(1).map(row => {
        const obj = {};
        r[0].forEach((k, idx) => { obj[k] = row[idx]; });
        return obj;
    }) : r;

    const out = list.map((c, i) => {
        const lc = {};
        for (let k in c) {
            if (k.trim().length === 1) lc[k.trim()] = c[k];
            else lc[k.trim().toLowerCase()] = c[k];
        }

        const subj = c.s || c.subject || lc.subject || lc.clean_s || lc.message || "";
        const m = subj.match(/^([a-zA-Z_-]+)(?:\(([^)]+)\))?:\s*(.*)$/);
        
        if (m) {
            c.t = m[1].toLowerCase();
            c.scope = m[2] || lc.scope || c.scope || 'global';
            c.clean_s = m[3];
        } else {
            const fallbackT = (lc.type || c.type || "").toLowerCase();
            c.t = (fallbackT && fallbackT !== 'commit') ? fallbackT : 'chore';
            c.scope = lc.scope || c.scope || 'global';
            c.clean_s = subj || 'unknown';
        }
        c.s = subj;
        c.p_type = c.t;

        c.tot = Number(c.tot ?? lc.total) || 0;
        for (let k in lc) {
            if (k.length === 1 && k >= 'A' && k <= 'Z') c[k] = Number(lc[k]) || 0;
        }
        
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
          
        let rawTier = String(c.tier || lc.tier || "").toLowerCase();
        if (rawTier.includes('critical') || rawTier.includes('pivotal')) c.tier = 'Pivotal';
        else if (rawTier.includes('significant') || rawTier.includes('core')) c.tier = 'Core';
        else if (rawTier.includes('routine') || rawTier.includes('minor')) c.tier = 'Minor';
        else {
            if (c.tot >= 10) c.tier = 'Pivotal';
            else if (c.tot >= 7) c.tier = 'Core';
            else c.tier = 'Minor';
        }

        // Direct integer pass-through for dynamic touches (No Zero-Collapse)
        for (let k in lc) {
            if (k.startsWith('touches_')) {
                const val = lc[k];
                if (val === "true" || val === true || val === "1") {
                    c[k] = 1;
                } else if (!isNaN(Number(val)) && Number(val) > 0) {
                    c[k] = Number(val);
                } else if (val === "false" || val === false || val === "0" || val === 0) {
                    // Explicitly dropped to prevent cross-rubric axis bleeding
                }
                // If it's empty, null, or undefined, we leave it off 'c' entirely to prevent cross-rubric key leakage.
            }
        }
          
        return c;
    });
    const MAP = { cord:['C','O','R','D'], ship:['S','H','I','P'], wave:['W','A','V','E'], grid:['G','R','I','D'], flux:['F','L','U','X'], form:['F','O','R','M'], lock:['L','O','C','K'], plan:['P','L','A','N'] };
    const rName = (new URLSearchParams(window.location.search).get("rubric") || "cord").toLowerCase().replace(/_mock$/i, '');
    
    if (MAP[rName]) {
        window.CM_ACTIVE_AXES = MAP[rName];
    } else {
        let rubricOrder = [];
        if (isCSV && r[0]) rubricOrder = r[0].filter(k => k.length === 1 && k >= 'A' && k <= 'Z');
        else if (list.length > 0) rubricOrder = Object.keys(list[0]).filter(k => k.length === 1 && k >= 'A' && k <= 'Z').sort();
        if (rubricOrder.length > 0) window.CM_ACTIVE_AXES = rubricOrder;
    }
    return out;
}
export function fmtCD(ts){ const d=new Date(ts*1000); const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]; return `${m[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}`; }
export function fmtTableDate(ts){ const d=new Date(ts*1000); const m=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]; return `${m[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}, '${String(d.getFullYear()).slice(-2)}`; }
export function fmtStr(ts){ const d=new Date(ts*1000); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
export function calcMAvg(arr, mode, cArr, isLin) {
    if(mode===0) return [];
    const collapse = (valMap) => {
        if (!isLin) return cArr.map(c => valMap[fmtStr(c.ts)]);
        let maxTs = {};
        cArr.forEach(c => { const d = fmtStr(c.ts); if (!maxTs[d] || c.ts > maxTs[d]) maxTs[d] = c.ts; });
        return Object.keys(valMap).map(d => ({ x: maxTs[d], y: valMap[d] })).sort((a, b) => a.x - b.x);
    };
    if(mode===1){ const w=5; let res = arr.map((_,i)=>{ const sl=arr.slice(Math.max(0,i-w+1),i+1); const a=sl.reduce((s,x)=>s+x,0)/sl.length; return isLin?{x:cArr[i].ts,y:parseFloat(a.toFixed(2))}:parseFloat(a.toFixed(2));}); if (isLin) res.sort((a, b) => a.x - b.x); return res; }
    if(mode===2){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); return collapse(mx); }
    if(mode===3){ let ds={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!ds[d])ds[d]=[]; ds[d].push(arr[i]); }); let md={}; Object.keys(ds).forEach(d=>{ const s=[...ds[d]].sort((a,b)=>a-b); const mid=Math.floor(s.length/2); md[d]=s.length%2!==0?s[mid]:(s[mid-1]+s[mid])/2; }); return collapse(md); }
    if(mode===4){ let dd={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!dd[d])dd[d]={s:0,c:0}; dd[d].s+=arr[i]; dd[d].c++; }); const dy=Object.keys(dd); let valMap={}; dy.forEach((d, ix)=>{ const sl=dy.slice(Math.max(0,ix-6),ix+1); let ts=0,tv=0; sl.forEach(dy=>{ts+=dd[dy].s;tv+=dd[dy].c;}); valMap[d]=tv>0?parseFloat((ts/tv).toFixed(2)):0; }); return collapse(valMap); }
    if(mode===5){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); const dy=Object.keys(mx); let valMap={}; dy.forEach((d, ix)=>{ const sl=dy.slice(Math.max(0,ix-6),ix+1); valMap[d]=Math.max(...sl.map(dy=>mx[dy])); }); return collapse(valMap); }
    return [];
}
export const getTop25 = (arr) => { const s=[...arr].sort((a,b)=>b-a); return s[Math.floor(s.length*0.25)] || 999; };
