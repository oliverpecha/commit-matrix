const formatTableDate = (ts) => {
    if (!ts) return "Unknown";
    const d = new Date(ts * 1000);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", '" + d.getFullYear().toString().slice(-2);
};

const parseCommit = (subject) => {
    const match = subject.match(/^([a-zA-Z]+)(?:\(([^)]+)\))?:\s*(.+)$/);
    if (match) return { type: match[1], scope: match[2] || "", desc: match[3] };
    return { type: "commit", scope: "", desc: subject };
};

const getTypeColor = (type) => {
    const map = { feat: "#5c91e0", fix: "#ff4b4b", style: "#e0d05c", refactor: "#8ed068", chore: "#aaa", docs: "#ffa726" };
    return map[type] || "#888";
};

const getScopeColor = (scope) => {
    const map = { scripts: "#e0d05c", proxy: "#68d08e", dashboard: "#c99ef0", core: "#e0d05c" };
    return map[scope] || "#aaa";
};

export function getTableColumns() {
    return [
        { label: "#", key: "n", align: "left" },
        { label: "AUTHORED", key: "ts", align: "left" },
        { label: "TYPE", key: "p_type", align: "left" },
        { label: "SCOPE", key: "p_scope", align: "left" },
        { label: "SUBJECT", key: "p_desc", align: "left" },
        { label: "TIER", key: "tot", align: "left" },
        { label: "C", key: "C", align: "center" },
        { label: "I", key: "I", align: "center" },
        { label: "R", key: "R", align: "center" },
        { label: "S", key: "S", align: "center" },
        { label: "D", key: "D", align: "center" },
        { label: "TOTAL", key: "tot", align: "center" },
        { label: "+", key: "lines_added", align: "center" },
        { label: "-", key: "lines_deleted", align: "center" },
        { label: "HASH", key: "h", align: "left" }
    ];
}

export function normalizeCommits(commits) {
    return (commits || []).map(c => {
        const p = parseCommit(c.s || c.subject || "");
        return {
            ...c,
            n: Number(c.n) || 0,
            ts: Number(c.ts) || 0,
            C: Number(c.C) || 0,
            I: Number(c.I) || 0,
            R: Number(c.R) || 0,
            S: Number(c.S) || 0,
            D: Number(c.D) || 0,
            tot: Number(c.tot) || 0,
            lines_added: Number(c.lines_added) || 0,
            lines_deleted: Number(c.lines_deleted) || 0,
            p_type: p.type,
            p_scope: p.scope,
            p_desc: p.desc
        };
    });
}

export function sortDisplayData(displayData, currentSort) {
    displayData.sort((a, b) => {
        let valA = a[currentSort.col];
        let valB = b[currentSort.col];

        const numericColumns = ["n", "C", "I", "R", "S", "D", "tot", "lines_added", "lines_deleted", "ts"];
        if (numericColumns.includes(currentSort.col)) {
            valA = Number(valA) || 0;
            valB = Number(valB) || 0;
            return currentSort.asc ? (valA - valB) : (valB - valA);
        }

        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();

        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });

    return displayData;
}

export function renderTableRows(displayData) {
    const repo = new URLSearchParams(window.location.search).get("repo") || "commit-matrix";

    return displayData.map((c) => {
        const tc = getTypeColor(c.p_type);
        const sc = getScopeColor(c.p_scope);
        const trC = c.tier === "Critical" ? "#ff4b4b" : c.tier === "Significant" ? "#ffb84d" : "#8ed068";

        return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='transparent'">
            <td style="padding:12px 8px; color:#7a7874; font-size:12px;">${c.n || "-"}</td>
            <td style="padding:12px 8px; color:#aaa; font-size:12px; white-space:nowrap;">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none;" title="View Commit">${formatTableDate(c.ts)}</a>
            </td>
            <td style="padding:12px 8px;"><span style="color:${tc}; background:${tc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${c.p_type}</span></td>
            <td style="padding:12px 8px;">${c.p_scope ? `<span style="color:${sc}; background:${sc}22; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;">${c.p_scope}</span>` : ""}</td>
            <td style="padding:12px 8px; color:#ddd; font-size:13px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${c.p_desc}">
                <a target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" style="color:inherit; text-decoration:none; display:block; overflow:hidden; text-overflow:ellipsis;" title="View Commit">${c.p_desc}</a>
            </td>
            <td style="padding:12px 8px;">
                <div style="display:inline-flex; align-items:center; gap:6px; border:1px solid ${trC}44; border-radius:12px; padding:3px 10px; background:${trC}11;">
                    <div style="width:8px; height:8px; border-radius:50%; background:${trC}; box-shadow:0 0 6px ${trC};"></div>
                    <span style="color:${trC}; font-weight:700; font-size:11px;">${c.tier || "N/A"}</span>
                </div>
            </td>
            <td style="padding:12px 8px; text-align:center; color:#5c91e0; font-weight:700; font-size:12px;">${c.C}</td>
            <td style="padding:12px 8px; text-align:center; color:#c99ef0; font-weight:700; font-size:12px;">${c.I}</td>
            <td style="padding:12px 8px; text-align:center; color:#ffb84d; font-weight:700; font-size:12px;">${c.R}</td>
            <td style="padding:12px 8px; text-align:center; color:#8ed068; font-weight:700; font-size:12px;">${c.S}</td>
            <td style="padding:12px 8px; text-align:center; color:#ff4b4b; font-weight:700; font-size:12px;">${c.D}</td>
            <td style="padding:12px 8px; text-align:center; font-weight:800; color:#fff; font-size:13px;">${c.tot}</td>
            <td style="padding:12px 8px; text-align:center; color:#8ed068; font-size:12px;">+${c.lines_added}</td>
            <td style="padding:12px 8px; text-align:center; color:#7a7874; font-size:12px;">-${c.lines_deleted}</td>
            <td style="padding:12px 8px;">
                <a class="bp-hash" target="_blank" rel="noopener noreferrer" href="https://github.com/oliverpecha/${repo}/commit/${c.h || c.hash_short}" title="View Commit">${(c.h || c.hash_short || "").toString().substring(0, 7)}</a>
            </td>
        </tr>`;
    }).join("");
}
