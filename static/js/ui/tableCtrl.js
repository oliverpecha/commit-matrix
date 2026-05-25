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

// Memory State for Live Sorting
let currentSort = { col: 'n', asc: false };

export function renderTable(commits) {
    const thead = document.getElementById('cm-thead');
    const tbody = document.getElementById('cm-tbody');
    if (!thead || !tbody) return;

    const columns = [
        { label: '#', key: 'n', align: 'left' },
        { label: 'AUTHORED', key: 'ts', align: 'left' },
        { label: 'TYPE', key: 'p_type', align: 'left' },
        { label: 'SCOPE', key: 'p_scope', align: 'left' },
        { label: 'SUBJECT', key: 'p_desc', align: 'left' },
        { label: 'TIER', key: 'tot', align: 'left' },
        { label: 'C', key: 'C', align: 'center' },
        { label: 'I', key: 'I', align: 'center' },
        { label: 'R', key: 'R', align: 'center' },
        { label: 'S', key: 'S', align: 'center' },
        { label: 'D', key: 'D', align: 'center' },
        { label: 'TOTAL', key: 'tot', align: 'center' },
        { label: '+', key: 'lines_added', align: 'center' },
        { label: '-', key: 'lines_deleted', align: 'center' },
        { label: 'HASH', key: 'h', align: 'left' }
    ];

    // ONLY build headers if they don't exist to protect event listeners
    if (thead.children.length === 0) {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const th = document.createElement('th');
            th.style.cssText = `text-align:${col.align}; padding:12px 8px; color:#7a7874; font-size:10px; font-weight:800; letter-spacing:1px; border-bottom:1px solid rgba(255,255,255,0.05); cursor:pointer; user-select:none; white-space:nowrap; transition: color 0.2s;`;
            th.innerHTML = `${col.label} <span class="sort-icon" style="font-size:10px; margin-left:4px;"></span>`;
            
            th.onclick = () => {
                if (currentSort.col === col.key) {
                    currentSort.asc = !currentSort.asc;
                } else {
                    currentSort.col = col.key;
                    currentSort.asc = false;
                }
                
                // Update UI carets visually
                Array.from(tr.children).forEach((childTh, idx) => {
                    const icon = childTh.querySelector('.sort-icon');
                    if (columns[idx].key === currentSort.col) {
                        childTh.style.color = '#fff';
                        icon.style.opacity = '1';
                        icon.textContent = currentSort.asc ? '▲' : '▼';
                    } else {
                        childTh.style.color = '#7a7874';
                        icon.textContent = '';
                    }
                });
                
                // Force an immediate re-render of the table body
                renderTable(window.MATRIX_PAYLOAD);
            };
            tr.appendChild(th);
        });
        thead.appendChild(tr);
        
        // Trigger initial caret visual state
        thead.querySelector('th').click(); 
        thead.querySelector('th').click(); // Double click sets to descending
    }

    // Process strings once for sorting and rendering
    let displayData = commits.map(c => {
        const p = parseCommit(c.s || c.subject || '');
        return { ...c, p_type: p.type, p_scope: p.scope, p_desc: p.desc };
    });

    // Apply Active Sort State
    displayData.sort((a, b) => {
        let valA = a[currentSort.col];
        let valB = b[currentSort.col];

        if (valA === undefined || valA === null) valA = '';
        if (valB === undefined || valB === null) valB = '';

        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });

    // Safely update the body
    tbody.innerHTML = displayData.map((c) => {
        const tc = getTypeColor(c.p_type);
        const sc = getScopeColor(c.p_scope);
        const trC = c.tier === 'Critical' ? '#ff4b4b' : c.tier === 'Significant' ? '#ffb84d' : '#8ed068';
        
        return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
            <td style="padding:12px 8px; color:#7a7874; font-size:12px;">${c.n || '-'}</td>
            <td style="padding:12px 8px; color:#aaa; font-size:12px; white-space:nowrap;">
                <a target="_blank" href="https://github.com/oliverpecha/${new URLSearchParams(window.location.search).get('repo') || 'commit-matrix'}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none;" title="View Commit">${formatTableDate(c.ts)}</a>
            </td>
            <td style="padding:12px 8px;">
                <span style="color:${tc}; background:${tc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${c.p_type}</span>
            </td>
            <td style="padding:12px 8px;">
                ${c.p_scope ? `<span style="color:${sc}; background:${sc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${c.p_scope}</span>` : ''}
            </td>
            <td style="padding:12px 8px; color:#ddd; font-size:13px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${c.p_desc}">
                <a target="_blank" href="https://github.com/oliverpecha/${new URLSearchParams(window.location.search).get('repo') || 'commit-matrix'}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none; display:block; overflow:hidden; text-overflow:ellipsis;" title="View Commit">${c.p_desc}</a>
            </td>
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
            <td style="padding:12px 8px;">
                <a class="bp-hash" target="_blank" href="https://github.com/oliverpecha/${new URLSearchParams(window.location.search).get('repo') || 'commit-matrix'}/commit/${c.h || c.hash_short}" title="View Commit">${(c.h || c.hash_short || '').toString().substring(0,7)}</a>
            </td>
        </tr>`;
    }).join('');
}
