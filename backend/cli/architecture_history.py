#!/usr/bin/env python3
"""
Architecture Blueprint history utility.

Lists Architecture Blueprints, their Generations, TreeSig, change_shape tag,
and generator metadata for a given repo (defaults to HOST_REPO_NAME).

Usage (from repo root):
    PYTHONPATH=. python3 backend/cli/architecture_history.py
    PYTHONPATH=. python3 backend/cli/architecture_history.py my-repo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.cli.architecture_history_data import build_history_report
from backend.cli.architecture_history_render import render_history_report


def _parse_args(argv: list[str]) -> tuple[str | None, bool]:
    repo_label = None
    reverse = False

    for arg in argv:
        if arg == "--reverse":
            reverse = True
        elif arg.startswith("-"):
            raise SystemExit(f"unknown flag: {arg}")
        elif repo_label is None:
            repo_label = arg
        else:
            raise SystemExit(f"unexpected extra argument: {arg}")

    return repo_label, reverse


def main(repo_label: str | None = None, reverse: bool = False) -> None:
    report = build_history_report(repo_label)
    render_history_report(report, reverse=reverse)


if __name__ == "__main__":
    repo_label, reverse = _parse_args(sys.argv[1:])
    main(repo_label, reverse=reverse)
