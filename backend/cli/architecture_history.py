#!/usr/bin/env python3
"""
Architecture Blueprint history utility.

Lists Architecture Blueprints, their Generations, TreeSig, change_shape tag,
and generator metadata for a given repo (defaults to HOST_REPO_NAME).

Usage (from repo root):
    PYTHONPATH=. python3 backend/cli/architecture_history.py
    PYTHONPATH=. python3 backend/cli/architecture_history.py my-repo
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.cli.architecture_history_data import (
    build_history_report,
    filter_history_report,
    history_report_to_dict,
)
from backend.cli.architecture_history_render import render_history_report


def _usage() -> str:
    return """usage: backend/cli/architecture_history.py [repo_label] [options]

Options:
  --reverse                 Show newest entries first.
  --compact                 Compact snapshot blocks and shorten commit rows.
  --show-operational        Show stash/recovery operational commits inline.
  --hide-operational        Collapse operational commits into omission summaries.
  --debug                   Enable extra architecture history debug telemetry.
  --json                    Emit machine-readable JSON instead of the text renderer.
  --since <id|sha|date>     Filter entries at or after a topo ID, SHA prefix, or YYYY-MM-DD date; numeric topo IDs match snapshot span overlap.
  --until <id|sha|date>     Filter entries at or before a topo ID, SHA prefix, or YYYY-MM-DD date; numeric topo IDs match snapshot span overlap.
  --generation <n>          Filter entries to a specific generation number.
  --sig <prefix>            Filter entries by snapshot TreeSig prefix.
  --sig-prefix <prefix>     Alias for --sig.
  --only-reappeared         Keep only snapshots that ran more than once.
  --llm-summarize           Reserved later-phase flag; not implemented yet.
  --help                    Show this help text.

Selector formats:
  - topo ID: integer like 153
  - SHA prefix: hex like a1b2c3d
  - date: YYYY-MM-DD like 2026-05-24

Notes:
  - Default behavior is equivalent to --show-operational.
  - In compact mode, operational commits are hidden by default unless --show-operational is passed.
  - --llm-summarize is intentionally tracked but not implemented in this phase.
  - If you do not pass repo_label, the command uses the repo name from HOST_REPO_NAME in your environment/config.
"""

def _parse_args(argv: list[str]) -> tuple[
    str | None,
    bool,
    bool,
    bool,
    bool,
    bool,
    str | None,
    str | None,
    int | None,
    str | None,
    bool,
    bool,
]:
    repo_label = None
    reverse = False
    compact = False
    show_operational = True
    debug = False
    json_mode = False
    since = None
    until = None
    generation = None
    sig_prefix = None
    only_reappeared = False
    llm_summarize = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--help":
            print(_usage())
            raise SystemExit(0)
        elif arg == "--reverse":
            reverse = True
        elif arg == "--compact":
            compact = True
        elif arg == "--show-operational":
            show_operational = True
        elif arg == "--hide-operational":
            show_operational = False
        elif arg == "--debug":
            debug = True
        elif arg == "--json":
            json_mode = True
        elif arg == "--only-reappeared":
            only_reappeared = True
        elif arg == "--llm-summarize":
            llm_summarize = True
        elif arg == "--since":
            if i + 1 >= len(argv):
                raise SystemExit(f"missing value for {arg}\n\n{_usage()}")
            since = argv[i + 1]
            i += 1
        elif arg == "--until":
            if i + 1 >= len(argv):
                raise SystemExit(f"missing value for {arg}\n\n{_usage()}")
            until = argv[i + 1]
            i += 1
        elif arg == "--generation":
            if i + 1 >= len(argv):
                raise SystemExit(f"missing value for {arg}\n\n{_usage()}")
            raw = argv[i + 1]
            if not raw.isdigit():
                raise SystemExit(f"--generation expects an integer, got: {raw}\n\n{_usage()}")
            generation = int(raw)
            i += 1
        elif arg in {"--sig", "--sig-prefix"}:
            if i + 1 >= len(argv):
                raise SystemExit(f"missing value for {arg}\n\n{_usage()}")
            sig_prefix = argv[i + 1]
            i += 1
        elif arg.startswith("-"):
            raise SystemExit(f"unknown flag: {arg}\n\n{_usage()}")
        elif repo_label is None:
            repo_label = arg
        else:
            raise SystemExit(f"unexpected extra argument: {arg}\n\n{_usage()}")
        i += 1

    if compact and "--show-operational" not in argv and "--hide-operational" not in argv:
        show_operational = False

    return (
        repo_label,
        reverse,
        compact,
        show_operational,
        debug,
        json_mode,
        since,
        until,
        generation,
        sig_prefix,
        only_reappeared,
        llm_summarize,
    )


def main(
    repo_label: str | None = None,
    reverse: bool = False,
    compact: bool = False,
    show_operational: bool = True,
    debug: bool = False,
    json_mode: bool = False,
    since: str | None = None,
    until: str | None = None,
    generation: int | None = None,
    sig_prefix: str | None = None,
    only_reappeared: bool = False,
    llm_summarize: bool = False,
) -> None:
    if llm_summarize:
        raise SystemExit("--llm-summarize is reserved for a later phase and is not implemented yet.")

    report = build_history_report(repo_label, debug=debug)
    report = filter_history_report(
        report,
        since=since,
        until=until,
        generation=generation,
        sig_prefix=sig_prefix,
        only_reappeared=only_reappeared,
    )

    if json_mode:
        payload = history_report_to_dict(report)
        payload["filters"] = {
            "since": since,
            "until": until,
            "generation": generation,
            "sig_prefix": sig_prefix,
            "only_reappeared": only_reappeared,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    render_history_report(
        report,
        reverse=reverse,
        compact=compact,
        show_operational=show_operational,
        since=since,
        until=until,
        generation=generation,
        sig_prefix=sig_prefix,
        only_reappeared=only_reappeared,
    )


if __name__ == "__main__":
    (
        repo_label,
        reverse,
        compact,
        show_operational,
        debug,
        json_mode,
        since,
        until,
        generation,
        sig_prefix,
        only_reappeared,
        llm_summarize,
    ) = _parse_args(sys.argv[1:])
    main(
        repo_label,
        reverse=reverse,
        compact=compact,
        show_operational=show_operational,
        debug=debug,
        json_mode=json_mode,
        since=since,
        until=until,
        generation=generation,
        sig_prefix=sig_prefix,
        only_reappeared=only_reappeared,
        llm_summarize=llm_summarize,
    )
