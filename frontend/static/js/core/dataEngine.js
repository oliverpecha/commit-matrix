import { getTierFromTotal } from '../constants/tiers.js?v=0.1.431';
export function filterByDateBounds(commits, startTs, endTs) {
    if (!Array.isArray(commits) || !commits.length) return [];
    if (!startTs && !endTs) return commits;
    return commits.filter(c => {
        const ts = c.ts || 0;
        if (startTs && ts < startTs) return false;
        if (endTs && ts > endTs) return false;
        return true;
    });
}
export function extractDynamicAxes(commits) { if (!commits || !commits.length) return []; const keys = new Set(); commits.forEach(c => Object.keys(c).forEach(k => { if (k.startsWith('touches_')) keys.add(k); })); return Array.from(keys).sort(); }
export function processCommits(r) {
    window.CM_AUDIT_ANOMALIES = [];
    if (!r || !r.length) return [];
    const isCSV = Array.isArray(r[0]);
    const list = isCSV ? r.slice(1).map(row => {
        const obj = {};
        r[0].forEach((k, idx) => { obj[k] = row[idx]; });
        return obj;
    }) : r;

    const out = list.map((cOrig, i) => {
        const c = { ...cOrig };
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
        
        if (cOrig.orig_ts !== undefined) {
            c.orig_ts = Number(cOrig.orig_ts);
            c.ts = c.orig_ts;
        } else if (c.ts) {
            c.orig_ts = Number(c.ts);
            c.ts = c.orig_ts;
        } else if (lc.date) {
            c.orig_ts = Math.floor(new Date(String(lc.date).replace("'", "20")).getTime() / 1000) || 0;
            c.ts = c.orig_ts;
        } else {
            c.orig_ts = 0;
            c.ts = 0;
        }

        c.n = Number(c.n ?? lc['#']) || (i + 1);
        c.lines_added = Number(c.lines_added ?? lc.additions) || 0;
        c.lines_deleted = Number(c.lines_deleted ?? lc.deletions) || 0;
        c.h = c.h || lc.hash || "";
          
        // Dynamically compute tier policy from raw total score using active UI strategy
        c.tier = getTierFromTotal(c.tot, (typeof UI_STATE !== 'undefined' && UI_STATE.tierDistribution) ? UI_STATE.tierDistribution : 'tight_floor');

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
        let mathSum = 0;
        let hasAxes = false;
        for (let k in lc) {
            if (k.length === 1 && k >= 'A' && k <= 'Z') { mathSum += (Number(lc[k]) || 0); hasAxes = true; }
        }
        let anomalyReasons = [];
        if (hasAxes && mathSum !== c.tot) anomalyReasons.push(`Sum of axes (${mathSum}) ≠ Total (${c.tot})`);
        
        c.model = lc.model || 'gemini/gemini-2.5-flash-lite (Legacy)';
        if (anomalyReasons.length > 0) {
            window.CM_AUDIT_ANOMALIES.push({ hash: c.h, num: c.n, ts: c.ts, subj: c.s, model: c.model, reasons: anomalyReasons });
        }
          
        return c;
    });
    // Stagger same-day commits evenly across 24 hours so bar charts don't eclipse each other
    const dayMap = {};
    out.forEach(c => {
        const baseDay = Math.floor((c.orig_ts || c.ts || 0) / 86400) * 86400;
        if (!dayMap[baseDay]) dayMap[baseDay] = [];
        dayMap[baseDay].push(c);
    });
    Object.values(dayMap).forEach(dayCommits => {
        if (dayCommits.length > 1) {
            dayCommits.sort((a, b) => (a.n || 0) - (b.n || 0));
            const step = 86400 / (dayCommits.length + 1);
            dayCommits.forEach((c, idx) => {
                const base = Math.floor((c.orig_ts || c.ts || 0) / 86400) * 86400;
                c.ts = base + Math.floor(step * (idx + 1));
            });
        }
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
        if (!isLin) return cArr.map(c => valMap[fmtStr(c.ts)] ?? 0);
        return cArr.map(c => ({ x: c.ts, y: valMap[fmtStr(c.ts)] ?? 0 })).sort((a, b) => a.x - b.x);
    };
    if(mode===1){ const w=5; let res = arr.map((_,i)=>{ const sl=arr.slice(Math.max(0,i-w+1),i+1); const a=sl.reduce((s,x)=>s+x,0)/sl.length; return isLin?{x:cArr[i].ts,y:parseFloat(a.toFixed(2))}:parseFloat(a.toFixed(2));}); if (isLin) res.sort((a, b) => a.x - b.x); return res; }
    if(mode===2){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); return collapse(mx); }
    if(mode===3){ let ds={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!ds[d])ds[d]=[]; ds[d].push(arr[i]); }); let md={}; Object.keys(ds).forEach(d=>{ const s=[...ds[d]].sort((a,b)=>a-b); const mid=Math.floor(s.length/2); md[d]=s.length%2!==0?s[mid]:(s[mid-1]+s[mid])/2; }); return collapse(md); }
    if(mode===4){ let dd={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!dd[d])dd[d]={s:0,c:0}; dd[d].s+=arr[i]; dd[d].c++; }); const dy=Object.keys(dd); let valMap={}; dy.forEach((d, ix)=>{ const sl=dy.slice(Math.max(0,ix-6),ix+1); let ts=0,tv=0; sl.forEach(dy=>{ts+=dd[dy].s;tv+=dd[dy].c;}); valMap[d]=tv>0?parseFloat((ts/tv).toFixed(2)):0; }); return collapse(valMap); }
    if(mode===5){ let mx={}; cArr.forEach((c,i)=>{ const d=fmtStr(c.ts); if(!mx[d]||arr[i]>mx[d]) mx[d]=arr[i]; }); const dy=Object.keys(mx); let valMap={}; dy.forEach((d, ix)=>{ const sl=dy.slice(Math.max(0,ix-6),ix+1); valMap[d]=Math.max(...sl.map(dy=>mx[dy])); }); return collapse(valMap); }
    return [];
}
export const getTop25 = (arr) => { const s=[...arr].sort((a,b)=>b-a); return s[Math.floor(s.length*0.25)] || 999; };
