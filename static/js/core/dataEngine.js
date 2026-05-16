export function processCommits(rawCommits) {
    return rawCommits.map(c => {
        const match = c.s.match(/^([a-zA-Z_-]+)(?:\(([^)]+)\))?:\s*(.*)$/);
        if (match) {
            c.t = match[1].toLowerCase();
            c.scope = match[2] || 'global';
            c.clean_s = match[3];
        } else {
            c.t = 'chore';
            c.scope = 'global';
            c.clean_s = c.s;
        }
        return c;
    });
}

export function fmtChartDate(ts) {
    const d = new Date(ts * 1000);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}`;
}

export function fmtTableDate(ts) {
    const d = new Date(ts * 1000);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2,'0')}, '${String(d.getFullYear()).slice(-2)}`;
}

export function fmtDateStr(ts) {
    const d = new Date(ts * 1000);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

export function calculateMovingAverage(dataArray, mode, commits, isLin) {
    if (mode === 0) return [];
    
    if (mode === 1) { // Trailing 5
        const WIN = 5;
        return dataArray.map((_, i) => {
            const slice = dataArray.slice(Math.max(0, i - WIN + 1), i + 1);
            const avg = slice.reduce((s, x) => s + x, 0) / slice.length;
            return isLin ? { x: commits[i].ts, y: parseFloat(avg.toFixed(2)) } : parseFloat(avg.toFixed(2));
        });
    }
    
    if (mode === 2) { // Daily Peak
        let dailyMax = {};
        commits.forEach((c, i) => {
            const d = fmtDateStr(c.ts);
            if (!dailyMax[d] || dataArray[i] > dailyMax[d]) dailyMax[d] = dataArray[i];
        });
        return commits.map((c, i) => isLin ? { x: c.ts, y: dailyMax[fmtDateStr(c.ts)] } : dailyMax[fmtDateStr(c.ts)]);
    }
    
    return []; // Extend placeholders as needed
}
