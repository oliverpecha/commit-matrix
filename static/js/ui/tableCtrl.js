// 1. Date Formatter matching "May 13, '26"
const formatTableDate = (ts) => {
    if (!ts) return 'Unknown';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ", '" + d.getFullYear().toString().slice(-2);
};

// 2. Regex Parser to extract Type, Scope, and Subject from conventional commits
const parseCommit = (subject) => {
    const match = subject.match(/^([a-zA-Z]+)(?:\(([^)]+)\))?:\s*(.+)$/);
    if (match) return { type: match[1], scope: match[2] || '', desc: match[3] };
    return { type: 'commit', scope: '', desc: subject };
};

// 3. Color Maps for Badges
const getTypeColor = (type) => {
    const map = { feat: '#5c91e0', fix: '#ff4b4b', style: '#e0d05c', refactor: '#8ed068', chore: '#aaa', docs: '#ffa726' };
    return map[type] || '#888';
};
const getScopeColor = (scope) => {
    const map = { scripts: '#e0d05c', proxy: '#68d08e', dashboard: '#c99ef0', core: '#e0d05c' };
    return map[scope] || '#aaa';
};

export function renderTable(commits) {
    const thead = document.getElementById('cm-thead');
    const tbody = document.getElementById('cm-tbody');
    if (!thead || !tbody) return;

    // Rebuild the 15 monolith columns
    const headers = ['#', 'AUTHORED', 'TYPE', 'SCOPE', 'SUBJECT', 'TIER', 'C', 'I', 'R', 'S', 'D', 'TOTAL', '+', '-', 'HASH'];
    
    thead.innerHTML = '<tr>' + headers.map(h => 
        `<th style="text-align:${['+','-','C','I','R','S','D','TOTAL'].includes(h)?'center':'left'}; padding:12px 8px; color:#7a7874; font-size:10px; font-weight:800; letter-spacing:1px; border-bottom:1px solid rgba(255,255,255,0.05);">${h}</th>`
    ).join('') + '</tr>';
    
    tbody.innerHTML = commits.slice().reverse().map((c, i) => {
        const p = parseCommit(c.s || c.subject || '');
        const tc = getTypeColor(p.type);
        const sc = getScopeColor(p.scope);
        const trC = c.tier === 'Critical' ? '#ff4b4b' : c.tier === 'Significant' ? '#ffb84d' : '#8ed068';
        const num = c.n || (commits.length - i);
        
        return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
            <td style="padding:12px 8px; color:#7a7874; font-size:12px;">${num}</td>
            <td style="padding:12px 8px; color:#aaa; font-size:12px; white-space:nowrap;">${formatTableDate(c.ts)}</td>
            
            <td style="padding:12px 8px;">
                <span style="color:${tc}; background:${tc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${p.type}</span>
            </td>
            
            <td style="padding:12px 8px;">
                ${p.scope ? `<span style="color:${sc}; background:${sc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${p.scope}</span>` : ''}
            </td>
            
            <td style="padding:12px 8px; color:#ddd; font-size:13px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${p.desc}">${p.desc}</td>
            
            <td style="padding:12px 8px;">
                <div style="display:inline-flex; align-items:center; gap:6px; border:1px solid ${trC}44; border-radius:12px; padding:3px 10px; background:${trC}11;">
                    <div style="width:8px; height:8px; border-radius:50%; background:${trC}; box-shadow:0 0 6px ${trC};"></div>
                    <span style="color:${trC}; font-weight:700; font-size:11px;">${c.tier || 'N/A'}</span>
                </div>
            </td>
            
            <td style="padding:12px 8px; text-align:center; color:#5c91e0; font-weight:700; font-size:12px;">${c.C !== undefined ? c.C : '-'}</td>
            <td style="padding:12px 8px; text-align:center; color:#c99ef0; font-weight:700; font-size:12px;">${c.I !== undefined ? c.I : '-'}</td>
            <td style="padding:12px 8px; text-align:center; color:#ffb84d; font-weight:700; font-size:12px;">${c.R !== undefined ? c.R : '-'}</td>
            <td style="padding:12px 8px; text-align:center; color:#8ed068; font-weight:700; font-size:12px;">${c.S !== undefined ? c.S : '-'}</td>
            <td style="padding:12px 8px; text-align:center; color:#ff4b4b; font-weight:700; font-size:12px;">${c.D !== undefined ? c.D : '-'}</td>
            <td style="padding:12px 8px; text-align:center; font-weight:800; color:#fff; font-size:13px;">${c.tot !== undefined ? c.tot : '-'}</td>
            
            <td style="padding:12px 8px; text-align:center; color:#8ed068; font-size:12px;">+${c.lines_added !== undefined ? c.lines_added : '-'}</td>
            <td style="padding:12px 8px; text-align:center; color:#7a7874; font-size:12px;">-${c.lines_deleted !== undefined ? c.lines_deleted : '-'}</td>
            
            <td style="padding:12px 8px; font-family:monospace; background:rgba(255,255,255,0.03); color:#888; font-size:11px; border-radius:4px;">${(c.h || c.hash_short || '').toString().substring(0,7)}</td>
        </tr>`;
    }).join('');
}
