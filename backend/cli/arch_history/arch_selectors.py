from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class SelectorCategory(Enum):
    TOPO_ID = auto()
    DATE = auto()
    COMMIT_SIG = auto()
    SNAPSHOT_SIG = auto()


@dataclass
class Selector:
    raw: str
    category: Optional[SelectorCategory]
    topo_id: Optional[int] = None
    date_iso: Optional[str] = None


class AmbiguousSigError(ValueError):
    """Raised when a hex-like prefix matches both commit_sig and snapshot_sig."""


class UnknownSigError(ValueError):
    """Raised when a hex-like prefix matches neither commit_sig nor snapshot_sig."""


def parse_selector(raw: str) -> Selector:
    """Classify a single raw selector into a category and parse topo_id/date.

    For hex-like tokens (6–40 hex chars), returns a Selector with category=None;
    later resolution (commit vs snapshot sig) will decide the final category.
    """
    value = (raw or "").strip()
    if not value:
        raise ValueError(
            "Invalid selector: empty string. Expected topo_id, commit_sig, snapshot_sig, or date (YYYY-MM-DD)."
        )

    if value.isdigit():
        return Selector(raw=value, category=SelectorCategory.TOPO_ID, topo_id=int(value))

    # date pattern YYYY-MM-DD (lightweight validation)
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return Selector(raw=value, category=SelectorCategory.DATE, date_iso=value)

    lowered = value.lower()
    # hex-like 6–40 chars
    if 6 <= len(lowered) <= 40 and all(c in "0123456789abcdef" for c in lowered):
        return Selector(raw=value, category=None)

    raise ValueError(
        f'Invalid selector value "{raw}". Expected one of: '
        "topo_id (integer), commit_sig (6–40 hex chars), snapshot_sig (6–40 hex chars), or date (YYYY-MM-DD)."
    )


def resolve_sig_category(selector: Selector, history: "HistoryReport") -> Selector:
    """Resolve a hex-like selector into COMMIT_SIG or SNAPSHOT_SIG by scanning history.

    - If matches only commit_sig(s) -> category COMMIT_SIG.
    - If matches only snapshot_sig(s) -> category SNAPSHOT_SIG.
    - If matches both -> raise AmbiguousSigError.
    - If matches neither -> raise UnknownSigError.

    For non-hex categories (TOPO_ID, DATE), returns selector unchanged.
    """
    # For already-resolved or non-sig selectors, return as-is.
    if selector.category in (SelectorCategory.TOPO_ID, SelectorCategory.DATE,
                             SelectorCategory.COMMIT_SIG, SelectorCategory.SNAPSHOT_SIG):
        return selector

    raw = (selector.raw or "").strip()
    lowered = raw.lower()
    if not (6 <= len(lowered) <= 40 and all(c in "0123456789abcdef" for c in lowered)):
        # Not a hex-like selector; leave unchanged.
        return selector

    # Lazy import to avoid circular dependency at module import time.
    from backend.services.architecture.models import SnapshotEntry, CommitRef  # type: ignore

    # Collect snapshot signatures.
    snapshot_sigs: set[str] = set()
    for entry in getattr(history, "entries", []):
        if isinstance(entry, SnapshotEntry):
            sig = getattr(entry, "snapshot_sig", None)
            if sig:
                snapshot_sigs.add(sig)

    # Collect commit signatures from all refs in all entries.
    commit_sigs: set[str] = set()
    for entry in getattr(history, "entries", []):
        if not isinstance(entry, SnapshotEntry):
            continue
        refs = []
        if entry.trigger:
            refs.append(entry.trigger)
        refs.extend(entry.successive_used_by)
        for run in entry.reappeared_runs:
            refs.extend(run)
        refs.extend(entry.also_used_by)
        for ref in refs:
            if isinstance(ref, CommitRef):
                sig = getattr(ref, "commit_sig", None)
                if sig:
                    commit_sigs.add(sig)

    matching_snapshots = {s for s in snapshot_sigs if s.lower().startswith(lowered)}
    matching_commits = {c for c in commit_sigs if c.lower().startswith(lowered)}

    if matching_snapshots and matching_commits:
        raise AmbiguousSigError(
            f'Hex-like selector "{raw}" is ambiguous: matches both commit and snapshot signatures.'
        )
    if matching_commits:
        return Selector(raw=selector.raw, category=SelectorCategory.COMMIT_SIG)
    if matching_snapshots:
        return Selector(raw=selector.raw, category=SelectorCategory.SNAPSHOT_SIG)

    raise UnknownSigError(
        f'Hex-like selector "{raw}" does not match any commit or snapshot signature in history.'
    )
