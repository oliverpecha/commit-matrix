#!/usr/bin/env python3
"""Health Check CLI - scan range and vacuum coverage for commit-matrix.

This CLI is the standalone owner of update_scan_range and detect_and_record_vacuums.
It decouples coverage tracking from the scoring pipeline.
"""

import argparse
import os
import sys

from backend.services.db.writer import update_scan_range, detect_and_record_vacuums
from backend.services.db.reader import read_scan_range, read_vacuums


def run_health_check(repo_label: str) -> int:
    # Derive db_path consistent with commit_pipeline / arch-history
    db_path = f"data/{repo_label}/db/{repo_label}.db"
    try:
        __import__("os").makedirs(__import__("os").path.dirname(db_path), exist_ok=True)
    except Exception:
        pass

    # Read current scan range from DB if present
    scan = read_scan_range(repo_label)
    vacuums = read_vacuums(repo_label)

    if scan:
        scan_head = scan.get("scan_head_topo")
        scan_tail = scan.get("scan_tail_topo")
    else:
        scan_head = None
        scan_tail = None

    # If we have an existing scan range, we re-run coverage bookkeeping
    # using the same head/tail; if not, we emit a warning.
    if scan_head is None or scan_tail is None:
        print(
            f"[health_check] no existing scan range for repo_label={repo_label}; "
            "run scoring pipeline first to establish baseline.",
            file=sys.stderr,
        )
        return 1

    try:
        update_scan_range(repo_label, scan_head, scan_tail)
        detect_and_record_vacuums(repo_label, scan_head, scan_tail)
    except Exception as e:
        print(f"[health_check] coverage persistence failed: {e}", file=sys.stderr)
        return 1

    # Print a brief summary
    scan = read_scan_range(repo_label)
    vacuums = read_vacuums(repo_label)
    total_vac = sum(v.get("commit_count", 0) for v in vacuums) if vacuums else 0

    print("─" * 71)
    print("🩺  Health Check Summary")
    if scan:
        print(
            f"    Scan Range   │ commits #{scan.get('scan_head_topo')} to #{scan.get('scan_tail_topo')}"
        )
    else:
        print("    Scan Range   │ (none recorded)")
    print(f"    Vacuums      │ {total_vac} unscanned commits")
    print("─" * 71)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run commit-matrix health check (scan/vacuum coverage)"
    )
    parser.add_argument(
        "--repo-label",
        type=str,
        default=os.environ.get("HOST_REPO_NAME", "commit-matrix"),
        help=(
            "Repository label used for DB paths "
            "(default from HOST_REPO_NAME or 'commit-matrix')"
        ),
    )
    args = parser.parse_args()

    repo_label = args.repo_label
    if repo_label in (".", "target_repo", "", "app", None):
        repo_label = "commit-matrix"

    rc = run_health_check(repo_label)
    sys.exit(rc)


if __name__ == "__main__":
    main()
