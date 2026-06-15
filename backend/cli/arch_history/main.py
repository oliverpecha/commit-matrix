#!/usr/bin/env python3
"""
Architecture Blueprint history utility.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.cli.arch_history.orchestrator import (
    build_history_report,
    filter_history_report,
    serialize_history_report_to_contract,
)
from backend.cli.arch_history.ui.render import render_history_report
from backend.cli.arch_history.arch_selectors import AmbiguousSigError, UnknownSigError

def _usage() -> str:
    return """usage: backend/cli/arch_history/main.py [repo_label] [options]

Options:
  --reverse                 Show newest entries first.
  --compact                 Compact snapshot blocks and shorten commit rows.
  --generation <n|n-m>      Filter by generation or range (e.g., 5-8).
  --snapshot <sig|sig-sig>  Filter by snapshot signature or range (e.g., a1b2-c3d4).
  --commit <id|id-id>       Filter by commit ID or range (e.g., 15-25 or a55a-b8bc).
  --since <date>            Filter entries from this YYYY-MM-DD date.
  --until <date>            Filter entries up to this YYYY-MM-DD date.
  --only-reappeared         Keep only snapshots that ran more than once.
  --show-operational        Show stash/recovery operational commits inline.
  --hide-operational        Collapse operational commits into omission summaries.
  --debug                   Enable extra architecture history debug telemetry.
  --json                    Emit machine-readable JSON instead of the text renderer.
  --fields <list>           Comma-separated entry fields to include (json mode only).
                            e.g. --fields flags,badges,lifespan_metrics
                            Always includes: generation, snapshot_sig.
  --llm-summarize           Reserved later-phase flag; not implemented yet.
  --help                    Show this help text.
"""

def _parse_args(argv: list[str]) -> tuple:
    repo_label = None
    reverse = False
    compact = False
    show_operational = True
    debug = False
    json_mode = False
    since = None
    until = None
    generation = None
    snapshot_prefix = None
    commit_target = None
    smart_target = None
    only_reappeared = False
    llm_summarize = False
    fields = None

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
        elif arg == "--fields":
            fields = argv[i + 1]; i += 1
        elif arg == "--since":
            since = argv[i + 1]; i += 1
        elif arg == "--until":
            until = argv[i + 1]; i += 1
        elif arg == "--generation":
            generation = argv[i + 1]; i += 1
        elif arg == "--snapshot":
            snapshot_prefix = argv[i + 1]; i += 1
        elif arg == "--commit":
            commit_target = argv[i + 1]; i += 1
        elif arg.startswith("-"):
            raise SystemExit(f"unknown flag: {arg}\n\n" + _usage())
        elif repo_label is None and Path(arg).is_dir():
            repo_label = arg
        elif smart_target is None:
            smart_target = arg
        else:
            raise SystemExit(f"unexpected extra argument: {arg}\n\n" + _usage())
        i += 1

    if compact and "--show-operational" not in argv and "--hide-operational" not in argv:
        show_operational = False

    return (
        repo_label, reverse, compact, show_operational, debug, json_mode,
        since, until, generation, snapshot_prefix, commit_target, smart_target, only_reappeared, llm_summarize, fields
    )

def main(
    repo_label: str | None = None, reverse: bool = False, compact: bool = False,
    show_operational: bool = True, debug: bool = False, json_mode: bool = False,
    since: str | None = None, until: str | None = None, generation: str | None = None,
    snapshot_prefix: str | None = None, commit_target: str | None = None,
    smart_target: str | None = None, only_reappeared: bool = False, llm_summarize: bool = False,
    fields: str | None = None,
) -> None:
    if llm_summarize:
        raise SystemExit("--llm-summarize is reserved for a later phase and is not implemented yet.")

    try:
        report = build_history_report(repo_label, debug=debug)
        report = filter_history_report(
            report, since=since, until=until, generation=generation,
            snapshot_prefix=snapshot_prefix, commit_target=commit_target,
            smart_target=smart_target, only_reappeared=only_reappeared,
        )
    except ValueError as e:
        raise SystemExit(f"Invalid selector: {e}")
    except (AmbiguousSigError, UnknownSigError) as e:
        print(f"arch-history: {e}", file=sys.stderr)
        raise SystemExit(2)

    if json_mode:
        payload = serialize_history_report_to_contract(report)
        payload["filters"] = {
            "since": since, "until": until, "generation": generation,
            "snapshot": snapshot_prefix, "commit": commit_target,
            "smart_target": smart_target, "only_reappeared": only_reappeared,
        }
        if fields:
            allowed = set(f.strip() for f in fields.split(","))
            # Always preserve structural keys
            always_keep = {"generation", "snapshot_sig"}
            allowed |= always_keep
            payload["entries"] = [
                {k: v for k, v in entry.items() if k in allowed}
                for entry in payload["entries"]
            ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    render_history_report(
        report, reverse=reverse, compact=compact, show_operational=show_operational,
        since=since, until=until, generation=generation, snapshot_prefix=snapshot_prefix,
        commit_target=commit_target, only_reappeared=only_reappeared,
    )

if __name__ == "__main__":
    (
        repo_label, reverse, compact, show_operational, debug, json_mode,
        since, until, generation, snapshot_prefix, commit_target, smart_target, only_reappeared, llm_summarize, fields
    ) = _parse_args(sys.argv[1:])
    
    main(
        repo_label, reverse=reverse, compact=compact, show_operational=show_operational,
        debug=debug, json_mode=json_mode, since=since, until=until, generation=generation,
        snapshot_prefix=snapshot_prefix, commit_target=commit_target, smart_target=smart_target,
        only_reappeared=only_reappeared, llm_summarize=llm_summarize, fields=fields
    )
