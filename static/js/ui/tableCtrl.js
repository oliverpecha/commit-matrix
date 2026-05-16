import { fmtTableDate } from '../core/dataEngine.js';
import { CM_COLORS, SC_CLASSES } from '../core/constants.js';

export function renderTable(commits, sortCol = 'n', sortDir = 'desc') {
    const tbody = document.getElementById('cm-tbody');
    const thead = document.getElementById('cm-thead');
    if (!tbody || !thead) return;

    // Minimal safe layout setup for the demo table columns
    thead.innerHTML = `<tr>
        <th data-col="n">#</th>
        <th data-col="date">Authored</th>
        <th data-col="t">Type</th>
        <th data-col="scope">Scope</th>
        <th>Subject</th>
        <th>Tier</th>
        <th style="text-align:center">Total</th>
        <th>Hash</th>
    </tr>`;

    const sorted = [...commits].sort((a, b) => {
        let av = a[sortCol], bv = b[sortCol];
        return sortDir === 'asc' ? (av > bv ? 1 : -1) : (bv > av ? 1 : -1);
    });

    tbody.innerHTML = '';
    sorted.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color:#7a7874">${c.n}</td>
            <td><span class="bp-date-link">${fmtTableDate(c.ts)}</span></td>
            <td><span class="bp-ct bp-ct-chore">${c.t}</span></td>
            <td><span class="bp-scope-tag ${SC_CLASSES[c.scope] || 'sc-docs'}">${c.scope}</span></td>
            <td><span class="bp-subj-link">${c.s}</span></td>
            <td><span class="bp-tier-badge" style="color:${CM_COLORS[c.tier]}">● ${c.tier}</span></td>
            <td style="text-align:center;font-weight:700;">${c.tot}</td>
            <td><span class="bp-hash">${c.h}</span></td>
        `;
        tbody.appendChild(tr);
    });
}
