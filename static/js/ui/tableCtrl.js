import { fmtTableDate } from '../core/dataEngine.js?v=2';
import { SC_CLASSES } from '../core/constants.js?v=2';

let currentSort = { col: 'n', dir: 'desc' };
let currentData = [];

export function renderTable(commits) {
    currentData = commits; const thead = document.getElementById('cm-thead'); if (!thead) return;
    const cols = [{ id:'n',lbl:'#'}, {id:'ts',lbl:'Authored'}, {id:'t',lbl:'Type'}, {id:'scope',lbl:'Scope'}, {id:'s',lbl:'Subject'}, {id:'tier',lbl:'Tier'}, {id:'C',lbl:'C',align:'center'}, {id:'I',lbl:'I',align:'center'}, {id:'R',lbl:'R',align:'center'}, {id:'S',lbl:'S',align:'center'}, {id:'D',lbl:'D',align:'center'}, {id:'tot',lbl:'Total',align:'center'}, {id:'la',lbl:'+',align:'right'}, {id:'ld',lbl:'-',align:'right'}, {id:'h',lbl:'Hash',align:'right'} ];
    thead.innerHTML = '<tr>' + cols.map(c => `<th data-col="${c.id}" ${c.align ? `style="text-align:${c.align}"` : ''}>${c.lbl}<span class="sa"></span></th>`).join('') + '</tr>';
    thead.querySelectorAll('th[data-col]').forEach(th => { th.addEventListener('click', () => { const col = th.getAttribute('data-col'); if (currentSort.col === col) currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc'; else { currentSort.col = col; currentSort.dir = 'desc'; } drawBody(); }); });
    drawBody();
}
function drawBody() {
    const tbody = document.getElementById('cm-tbody'), thead = document.getElementById('cm-thead'); if (!tbody) return;
    thead.querySelectorAll('th').forEach(th => { th.className = ''; if (th.getAttribute('data-col') === currentSort.col) th.classList.add(currentSort.dir === 'asc' ? 'sort-asc' : 'sort-desc'); });
    const sorted = [...currentData].sort((a, b) => { let av = a[currentSort.col], bv = b[currentSort.col]; if(typeof av==='string')av=av.toLowerCase(); if(typeof bv==='string')bv=bv.toLowerCase(); if(av<bv) return currentSort.dir==='asc'?-1:1; if(av>bv) return currentSort.dir==='asc'?1:-1; return 0; });
    tbody.innerHTML = '';
    sorted.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td style="color:#7a7874">${c.n}</td><td><span class="bp-date-link">${fmtTableDate(c.ts)}</span></td><td><span class="bp-ct bp-ct-${c.t==='feat'?'feat':c.t==='fix'?'fix':c.t==='docs'?'docs':'chore'}">${c.t}</span></td><td><span class="bp-scope-tag ${SC_CLASSES[c.scope] || 'sc-docs'}">${c.scope}</span></td><td><span class="bp-subj-link" title="${c.clean_s || c.s}">${c.clean_s || c.s}</span></td><td><span class="bp-tier-badge bp-tb-${c.tier==='Critical'?'crit':c.tier==='Significant'?'sig':'rout'}">● ${c.tier}</span></td><td style="text-align:center;color:#7a7874">${c.C}</td><td style="text-align:center;color:#7a7874">${c.I}</td><td style="text-align:center;color:#7a7874">${c.R}</td><td style="text-align:center;color:#7a7874">${c.S}</td><td style="text-align:center;color:#7a7874">${c.D}</td><td style="text-align:center;font-weight:700;">${c.tot}</td><td style="text-align:right;color:#8ed068;font-family:monospace">+${c.la}</td><td style="text-align:right;color:#ff4b4b;font-family:monospace">-${c.ld}</td><td style="text-align:right"><span class="bp-hash">${c.h}</span></td>`;
        tbody.appendChild(tr);
    });
}
