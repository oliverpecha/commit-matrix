from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.architecture.arch_builder import ensure_fresh_architecture_context


@dataclass
class ArchitectureState:
    signature: str | None
    gen: int | None
    change_shape: str | None
    mode: str | None
    summary: str
    established: bool
    advanced: bool
    available: bool


class ArchitectureResolver:
    def __init__(self, repo_path: str, max_retries: int = 3):
        self.repo_path = repo_path
        self.max_retries = max_retries
        self.prev_signature: str | None = None
        self.prev_gen = 0

    def resolve_for_commit(self, commit_sha: str, topo_id: int | None = None) -> tuple[ArchitectureState, dict[str, Any]]:
        result = None

        for _ in range(self.max_retries):
            try:
                result = ensure_fresh_architecture_context(self.repo_path, commit_sha=commit_sha, topo_id=topo_id)
                if result and getattr(result, "status", None) and getattr(result.status, "name", "") != "FAILED":
                    break
            except Exception:
                result = None

        if not result or getattr(result, "status", None) is None or getattr(result.status, "name", "") == "FAILED":
            state = ArchitectureState(
                signature=None,
                gen=self.prev_gen or None,
                change_shape=None,
                mode=None,
                summary="Architecture unavailable after retries; scoring continued without architecture context.",
                established=False,
                advanced=False,
                available=False,
            )
            return state, {}

        meta = result.metadata or {}
        sig = meta.get("tree_signature")
        cs = meta.get("change_summary") or {}
        change_shape = cs.get("change_shape") or "leaf-only"
        mode = meta.get("mode") or cs.get("mode") or "unknown"

        if self.prev_signature is None:
            gen = 1
            established = True
            advanced = False
            change_shape = "major:head"
            summary = "Architecture Head established for this scan."
        elif sig == self.prev_signature:
            gen = self.prev_gen
            established = False
            advanced = False
            summary = "Architecture unchanged — same era."
        elif str(change_shape).startswith("major:") or str(change_shape).startswith("multi-dir:"):
            gen = self.prev_gen + 1
            established = False
            advanced = True
            summary = "New architectural boundary — structural shift detected."
        else:
            gen = self.prev_gen
            established = False
            advanced = False
            summary = "Architecture updated — incremental change within current era."

        self.prev_signature = sig
        self.prev_gen = gen

        state = ArchitectureState(
            signature=sig,
            gen=gen,
            change_shape=change_shape,
            mode=mode,
            summary=summary,
            established=established,
            advanced=advanced,
            available=True,
        )
        return state, meta
