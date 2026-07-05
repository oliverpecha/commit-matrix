from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CommitWorkItem:
    topo_id: int
    commit_parts: tuple
    total_unscanned: int
    processed_count: int
    ordinal_in_window: int
    model_name: str
    rubric_path: str
    arch_context: str
    arch_tree_signature: str | None
    arch_gen: int | None
    arch_meta: dict[str, Any] | None = None
    arch_change_shape: str | None = None
    # Snapshot relationship fields — populated by pipeline, consumed by flush loop
    _snap_sig: str | None = None
    _snap_gen: int | None = None
    _snap_reappeared: bool = False
