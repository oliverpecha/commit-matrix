export function stripAnsi(chunk) {
    return chunk.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "");
}

export function normalizeSpacing(chunk) {
    return chunk
        .replace(/(📦 Discovered \d+ unscanned commits\.)(\n?)(🛡️ TOKEN SAVER ACTIVE:)/g, "$1\n\n$3")
        .replace(/\n{3,}/g, "\n\n");
}

export function normalizeWarnings(chunk) {
    return chunk.replace(
        /⚠️ Engine cleanup race detected while resolving final container state\. Stream output above is authoritative\.\n?/g,
        ""
    );
}

export function humanizeCopy(chunk) {
    return chunk.replace(
        /🛡️ TOKEN SAVER ACTIVE: Throttling queue to the \d+ newest\./g,
        (m) => {
            const n = (m.match(/(\d+)/) || [null, "15"])[1];
            return `🛡️ TOKEN SAVER ACTIVE: Focusing on the ${n} newest commits for this run.`;
        }
    );
}

export function formatTerminalChunk(chunk) {
    return humanizeCopy(normalizeWarnings(normalizeSpacing(stripAnsi(chunk))));
}
