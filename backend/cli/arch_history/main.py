#!/usr/bin/env python3
"""
Architecture Blueprint history utility.
"""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
# DB-first history loader is now the default. Legacy filesystem reconstruction
# is available only when MATRIX_LEGACY_HISTORY is set.
USE_DB_HISTORY = True
USE_LEGACY_HISTORY = bool(os.environ.get("MATRIX_LEGACY_HISTORY", "").strip())

from backend.cli.arch_history.orchestrator import (
    build_history_report,
    filter_history_report,
    serialize_history_report_to_contract,
    load_history_report_from_db,
)
from backend.cli.arch_history.ui.render import render_history_report
from backend.cli.arch_history.arch_selectors import AmbiguousSigError, UnknownSigError

def _usage() -> str:
    return """usage: backend/cli/arch_history/main.py [repo_label] [options]

Options:
  --chronological           Sort oldest boundary first (default is newest first).
  --compact                 Compact snapshot blocks and shorten commit rows.
  --last <n>                Scan only the last N commits from HEAD (pipeline-level).
  --back <n>                Show only the last N boundaries from HEAD.
  --back-snapshot <n>       Show only the last N snapshots from HEAD.
  --back-commit <n>         Show only the last N commits from HEAD.
  --boundary <n|n-m>        Filter by boundary number or range (e.g., 5-8).
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
  --db-path <path>          SQLite database path (default: data/{repo}/commit_matrix.db).
  --llm-summarize           Reserved later-phase flag; not implemented yet.
  --help                    Show this help text.
"""

def _parse_args(argv: list[str]) -> tuple:
    repo_label = None
    reverse = True
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
    back = None
    db_path = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--help":
            print(_usage())
            raise SystemExit(0)
        elif arg == "--reverse" or arg == "--chronological":
            reverse = False
        elif arg == "--last":
            import os as _os
            _os.environ["MATRIX_MAX_COMMITS"] = argv[i + 1]; i += 1
        elif arg == "--back":
            back = argv[i + 1]; i += 1
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
        elif arg == "--db-path":
            db_path = argv[i + 1]; i += 1
        elif arg == "--since":
            since = argv[i + 1]; i += 1
        elif arg == "--until":
            until = argv[i + 1]; i += 1
        elif arg == "--generation" or arg == "--boundary":
            generation = argv[i + 1]; i += 1
        elif arg == "--back-snapshot":
            back = f"snapshot:{argv[i + 1]}"; i += 1
        elif arg == "--back-commit":
            back = f"commit:{argv[i + 1]}"; i += 1
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
        since, until, generation, snapshot_prefix, commit_target, smart_target, only_reappeared, llm_summarize, fields, db_path, back
    )

def main(
    repo_label: str | None = None, reverse: bool = False, compact: bool = False,
    show_operational: bool = True, debug: bool = False, json_mode: bool = False,
    since: str | None = None, until: str | None = None, generation: str | None = None,
    snapshot_prefix: str | None = None, commit_target: str | None = None,
    smart_target: str | None = None, only_reappeared: bool = False, llm_summarize: bool = False,
    fields: str | None = None,
    db_path: str | None = None,
    back: str | None = None,
) -> None:
    if llm_summarize:
        raise SystemExit("--llm-summarize is reserved for a later phase and is not implemented yet.")

    try:
        if not json_mode:
            from backend.cli.arch_history.ui.progress import render_progress
            _progress_cb = render_progress
        else:
            _progress_cb = None
        if USE_LEGACY_HISTORY:
            # Legacy builder path (CSV/filesystem reconstruction)
            report = build_history_report(repo_label, debug=debug, on_progress=_progress_cb)
        else:
            # DB-first history loader (default)
            try:
                report = load_history_report_from_db(repo_label, db_path=db_path)
            except RuntimeError as e:
                msg = str(e)
                if "No commit_matrix.db found" in msg:
                    print(
                        "\n  No architecture runs are available yet; "
                        "run `commit-matrix .` to populate the database,\n"
                        "  or `arch-history --help` for usage details.\n"
                    )
                    return
                raise

        # Hydrate identity and summary totals for DB-first history.
        # This keeps legacy behavior when the DB loader omits aggregates.
        def _hydrate_identity(report_obj, repo_label_obj: str | None):
            if repo_label_obj and not getattr(report_obj, "repo_label", None):
                report_obj.repo_label = repo_label_obj
            if not getattr(report_obj, "repo_display", None):
                # Fallback: use repo_label as display if nothing richer is set.
                report_obj.repo_display = getattr(report_obj, "repo_label", None) or repo_label_obj

        def _hydrate_totals(report_obj):
            entries = getattr(report_obj, "entries", []) or []
            # Commits: derive from topo_id range if not already set.
            if not getattr(report_obj, "total_commits", None):
                topoids = [
                    e.trigger.topo_id
                    for e in entries
                    if getattr(e, "trigger", None) and e.trigger.topo_id is not None
                ]
                if topoids:
                    report_obj.total_commits = max(topoids) - min(topoids) + 1
                else:
                    report_obj.total_commits = 0
            # Snapshots and boundaries from entries.
            report_obj.total_blueprints = len(entries)
            report_obj.total_generations = len({getattr(e, "generation", None) for e in entries})

        report = filter_history_report(
            report, since=since, until=until, generation=generation,
            snapshot_prefix=snapshot_prefix, commit_target=commit_target,
            smart_target=smart_target, only_reappeared=only_reappeared,
        )
        _hydrate_identity(report, repo_label)
        _hydrate_totals(report)
        # --back N: limit results to N most recent items from HEAD
        if back is not None:
            if back.startswith("snapshot:"):
                n = int(back.split(":")[1])
                sorted_entries = sorted(
                    report.entries,
                    key=lambda e: e.trigger.topo_id if e.trigger and e.trigger.topo_id is not None else 0,
                    reverse=True,
                )[:n]
                keep_sigs = {e.snapshot_sig for e in sorted_entries}
                report.entries = [e for e in report.entries if e.snapshot_sig in keep_sigs]
            elif back.startswith("commit:"):
                n = int(back.split(":")[1])
                # Filter entries whose trigger is within the last N topo_ids
                all_topos = sorted(
                    [e.trigger.topo_id for e in report.entries if e.trigger and e.trigger.topo_id is not None],
                    reverse=True,
                )
                cutoff = all_topos[min(n - 1, len(all_topos) - 1)] if all_topos else 0
                report.entries = [e for e in report.entries if e.trigger and e.trigger.topo_id is not None and e.trigger.topo_id >= cutoff]
            else:
                n = int(back)
                gens = sorted({e.generation for e in report.entries}, reverse=True)[:n]
                if gens:
                    report.entries = [e for e in report.entries if e.generation in set(gens)]
            # Recompute summaries after filtering
            from backend.cli.arch_history.data.metrics import _compute_generation_summaries
            report.generation_summaries = _compute_generation_summaries(report.entries) if report.entries else {}
            report.total_blueprints = len(report.entries)
            report.total_generations = len({e.generation for e in report.entries})
        if _progress_cb and any([since, until, generation, snapshot_prefix, commit_target]):
            _progress_cb("filter_applied", {
                "since": since, "until": until, "generation": generation,
                "snapshot": snapshot_prefix, "commit": commit_target,
            })
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
        # JSON mode is strictly read-only; no DB writes here.
        return

    # arch-history default path is now read-only; DB rebuild is reserved for a separate maintenance tool.
    # If a rebuild mode is added later, it should live in a distinct command and never run on simple view invocations.
    render_history_report(
        report, reverse=reverse, compact=compact, show_operational=show_operational,
        since=since, until=until, generation=generation, snapshot_prefix=snapshot_prefix,
        commit_target=commit_target, only_reappeared=only_reappeared,
    )

if __name__ == "__main__":
    (
        repo_label, reverse, compact, show_operational, debug, json_mode,
        since, until, generation, snapshot_prefix, commit_target, smart_target, only_reappeared, llm_summarize, fields, db_path, back
    ) = _parse_args(sys.argv[1:])
    
    main(
        repo_label, reverse=reverse, compact=compact, show_operational=show_operational,
        debug=debug, json_mode=json_mode, since=since, until=until, generation=generation,
        snapshot_prefix=snapshot_prefix, commit_target=commit_target, smart_target=smart_target,
        only_reappeared=only_reappeared, llm_summarize=llm_summarize, fields=fields,
        db_path=db_path,
        back=back
    )
