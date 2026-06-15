# Architecture History API & MCP — Path to Implementation

**Prepared by:** Agent Marlowe (Maiden Name: Voss)
**Date:** June 15, 2026
**Contract Version:** 1.0
**Status:** CLI complete, HTTP and MCP pending

---

## 1. Current State

### What exists and works

| Component | Status | Location |
|-----------|--------|----------|
| Orchestrator (build, filter, serialize) | ✅ Production | `backend/cli/arch_history/orchestrator.py` |
| Contract serializer (`serialize_history_report_to_contract`) | ✅ Production | `backend/cli/arch_history/orchestrator.py` |
| Flags/badges derivation (`derive_badges`) | ✅ Production | `backend/cli/arch_history/orchestrator.py` |
| Taxonomy boundary layer | ✅ Production | `backend/cli/arch_history/taxonomy.py` |
| Boundary magnitude mapping | ✅ Production | `backend/cli/arch_history/taxonomy.py` → `MAGNITUDE_BY_NORMALIZED_TAG` |
| Internal data models | ✅ Production | `backend/cli/arch_history/models.py` |
| Boundary dataclasses | ✅ Production | `backend/cli/arch_history/models.py` → `BoundaryInfo`, `BoundaryScope`, `DisplacedSnapshot` |
| Generation boundary rationale (`boundary` object) | ✅ Production | `backend/cli/arch_history/orchestrator.py` → `_compute_generation_boundaries` |
| CLI entry point (`--json`, `--fields`, all filters) | ✅ Production | `backend/cli/arch_history/main.py` |
| Contract tests (67 passing) | ✅ Production | `backend/tests/test_history_serialization_contract.py` |
| UI renderer tests (real dataclasses) | ✅ Production | `backend/tests/test_cli_history.py` |
| Data transformation tests | ✅ Production | `backend/tests/test_data_transformations.py` |
| Versioned contract documentation | ✅ Production | `docs/architecture_history_metric_contract.md` |

### The three core functions everything builds on

Every downstream consumer (CLI, HTTP, MCP) calls the same three functions:

```python
from backend.cli.arch_history.orchestrator import (
    build_history_report,
    filter_history_report,
    serialize_history_report_to_contract,
)

# 1. Build — walks git history, loads ledger, computes metrics
report = build_history_report(repo_label)

# 2. Filter — applies since/until/generation/snapshot/commit selectors
report = filter_history_report(
    report,
    since=since,
    until=until,
    generation=generation,
    snapshot_prefix=snapshot,
    commit_target=commit,
    only_reappeared=only_reappeared,
)

# 3. Serialize — produces stable external JSON contract
payload = serialize_history_report_to_contract(report)

--fields filtering (already implemented in CLI)

Python

ALWAYS_KEEP = {"generation", "snapshot_sig"}

if fields_param:
    allowed = set(f.strip() for f in fields_param.split(",")) | ALWAYS_KEEP
    payload["entries"] = [
        {k: v for k, v in entry.items() if k in allowed}
        for entry in payload["entries"]
    ]

This exact logic is reused verbatim in both the HTTP controller and MCP server.
Contract payload shape (v1.0)

JSON

{
  "contract_version": "1.0",
  "repo_label": "commit-matrix",
  "repo_display": "oliverpecha/commit-matrix",
  "total_commits": 64,
  "total_blueprints": 39,
  "total_generations": 10,
  "current": {
    "snapshot_sig": "d14baf25073d0302...",
    "generated_at": "2026-06-15 12:26:52",
    "generator_version": "archgen-v1",
    "mode": "programmatic",
    "shape": "multi-dir:default",
    "total_files": 1241,
    "selected_files": 8
  },
  "entries": [
    {
      "generation": 1,
      "generation_index": 0,
      "snapshot_sig": "60859c3eeca2e317...",
      "shape": "major:first-generation",
      "shape_label": "Architecture Baseline Established",
      "generator_version": "archgen-v1",
      "mode": "programmatic",
      "generated_at": "2026-06-15 12:22:13",
      "size_bytes": 1446,
      "selected_files": 8,
      "total_files": 15,
      "trigger": {
        "commit_sig": "962d562",
        "topo_id": 1,
        "date": "May 16, '26",
        "date_iso": "2026-05-16",
        "subject": "initialize CommitMatrix scaffold..."
      },
      "also_used_by": [],
      "successive_used_by": [],
      "reappeared_runs": [],
      "flags": {
        "is_current": false,
        "is_dominant": true,
        "lifespan_class": "short"
      },
      "badges": ["dominant", "short_lived"],
      "lifespan_metrics": {
        "total_commits": 1,
        "run_count": 1,
        "first_seen_topo_id": 1,
        "last_seen_topo_id": 1,
        "first_seen_date": "May 16, '26",
        "last_seen_date": "May 16, '26",
        "longest_streak": 1
      },
      "composition_metrics": {
        "successive_commit_count": 0,
        "reappeared_commit_count": 0,
        "operational_commit_count": 0,
        "development_commit_count": 1
      },
      "dominance_metrics": {
        "effective_commits": 1,
        "share_of_generation": 1.0
      }
    }
  ],
  "generation_summaries": {
    "1": {
      "generation": 1,
      "cause_tag": "genesis",
      "cause_label": "Architecture Baseline Established",
      "generation_distinct_commit_count": 1,
      "snapshot_count": 1,
      "structural_count": 1,
      "incremental_count": 0,
      "dominant_snapshot_sig": "60859c3eeca2e317...",
      "dominant_effective_commits": 1,
      "dominant_share_of_generation": 1.0,
      "repeated_treesig_count": 0,
      "boundary": {
        "cause_tag": "genesis",
        "cause_label": "Architecture Baseline Established",
        "magnitude": "major",
        "commit": {
          "commit_sig": "962d562",
          "topo_id": 1,
          "date": "May 16, '26",
          "date_iso": "2026-05-16",
          "subject": "initialize CommitMatrix scaffold..."
        },
        "scope": {
          "top_level_dirs": ["backend", "static", "templates"],
          "file_count": 15
        },
        "displaced": null
      }
    }
  },
  "filters": {
    "since": null,
    "until": null,
    "generation": null,
    "snapshot": null,
    "commit": null,
    "smart_target": null,
    "only_reappeared": false
  }
}

Key design rules

    flags is authoritative. Agents, CI, policy logic use flags exclusively.
    badges is derived, read-only. badges == derive_badges(flags) must always hold.
    lifespan_class consolidates is_long_lived/is_short_lived into one enum.
    dominance_metrics contains only effective_commits and share_of_generation.
    cause_tag/cause_label are routed through taxonomy.py boundary functions.
    boundary object on each generation summary provides full rationale: cause, magnitude, commit, scope, displaced.
    Generation summary keys are deliberately serialized as strings.
    CONTRACT_VERSION is a module-level constant. Additive changes don't bump it.

Validated metrics (June 15, 2026)
Metric	Value
Snapshots	39
Generations	10
Commits	64
Full payload size	~77KB
--fields flags,badges payload	~17KB
Badge invariant violations	0
Boundary objects on generation summaries	10/10
Test count	67 passing
2. HTTP API Implementation
Architecture

text

GET /api/arch-history?generation=5&fields=flags,badges&since=2026-05-20
         |
         v
+------------------------------------------------------+
|  Controller (thin routing glue, ~30 lines)           |
|                                                      |
|  1. Parse query params                               |
|  2. build_history_report()                           |
|  3. filter_history_report(report, **params)          |
|  4. serialize_history_report_to_contract(report)     |
|  5. Apply ?fields= filtering                         |
|  6. Return JSON response                             |
+------------------------------------------------------+

Reference implementation (Flask)

Python

# backend/controllers/arch_history_controller.py

from flask import request, jsonify
from backend.cli.arch_history.orchestrator import (
    build_history_report,
    filter_history_report,
    serialize_history_report_to_contract,
)

ALWAYS_KEEP = {"generation", "snapshot_sig"}

def get_architecture_history():
    report = build_history_report()
    report = filter_history_report(
        report,
        since=request.args.get("since"),
        until=request.args.get("until"),
        generation=request.args.get("generation"),
        snapshot_prefix=request.args.get("snapshot"),
        commit_target=request.args.get("commit"),
        only_reappeared=request.args.get("only_reappeared") == "true",
    )
    payload = serialize_history_report_to_contract(report)
    fields_param = request.args.get("fields")
    if fields_param:
        allowed = set(f.strip() for f in fields_param.split(",")) | ALWAYS_KEEP
        payload["entries"] = [
            {k: v for k, v in entry.items() if k in allowed}
            for entry in payload["entries"]
        ]
    return jsonify(payload)

FastAPI equivalent

Python

from fastapi import FastAPI, Query
from backend.cli.arch_history.orchestrator import (
    build_history_report, filter_history_report,
    serialize_history_report_to_contract,
)

app = FastAPI()
ALWAYS_KEEP = {"generation", "snapshot_sig"}

@app.get("/api/arch-history")
def get_architecture_history(
    generation: str | None = None, since: str | None = None,
    until: str | None = None, snapshot: str | None = None,
    commit: str | None = None, only_reappeared: bool = False,
    fields: str | None = None,
):
    report = build_history_report()
    report = filter_history_report(
        report, since=since, until=until, generation=generation,
        snapshot_prefix=snapshot, commit_target=commit,
        only_reappeared=only_reappeared,
    )
    payload = serialize_history_report_to_contract(report)
    if fields:
        allowed = set(f.strip() for f in fields.split(",")) | ALWAYS_KEEP
        payload["entries"] = [
            {k: v for k, v in entry.items() if k in allowed}
            for entry in payload["entries"]
        ]
    return payload

3. MCP Server Implementation
What MCP adds beyond HTTP
Layer	HTTP Controller	MCP Server
Transport	HTTP request/response	stdio (local) or SSE (remote)
Protocol	REST + query params	JSON-RPC 2.0 (tools/call, tools/list)
Schema	OpenAPI / Swagger	MCP inputSchema in tool definition
Discovery	Docs page	tools/list — agents auto-discover available tools
Reference implementation

Python

# backend/mcp/arch_history_server.py

import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from backend.cli.arch_history.orchestrator import (
    build_history_report, filter_history_report,
    serialize_history_report_to_contract,
)

server = Server("commit-matrix-arch-history")
ALWAYS_KEEP = {"generation", "snapshot_sig"}

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_architecture_history",
            description=(
                "Returns the architecture evolution history of the repository. "
                "Each entry is a snapshot with flags (canonical state), badges "
                "(derived presentation tokens), lifespan/composition/dominance "
                "metrics, and commit graph references. Generation summaries "
                "include boundary rationale with magnitude, scope, and "
                "displaced snapshot linkage."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "generation": {
                        "type": "string",
                        "description": "Generation number or range, e.g. '3' or '2-5'",
                    },
                    "since": {
                        "type": "string",
                        "description": "Start date filter (YYYY-MM-DD)",
                    },
                    "until": {
                        "type": "string",
                        "description": "End date filter (YYYY-MM-DD)",
                    },
                    "snapshot": {
                        "type": "string",
                        "description": "Snapshot signature prefix filter",
                    },
                    "commit": {
                        "type": "string",
                        "description": "Commit signature or topo ID filter",
                    },
                    "only_reappeared": {
                        "type": "boolean",
                        "description": "Keep only snapshots with run_count > 1",
                        "default": False,
                    },
                    "fields": {
                        "type": "string",
                        "description": (
                            "Comma-separated entry fields to include. "
                            "e.g. 'flags,badges,lifespan_metrics'. "
                            "Always includes: generation, snapshot_sig."
                        ),
                    },
                },
                "required": [],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name != "get_architecture_history":
        raise ValueError(f"Unknown tool: {name}")

    report = await asyncio.to_thread(build_history_report)
    report = filter_history_report(
        report,
        since=arguments.get("since"),
        until=arguments.get("until"),
        generation=arguments.get("generation"),
        snapshot_prefix=arguments.get("snapshot"),
        commit_target=arguments.get("commit"),
        only_reappeared=arguments.get("only_reappeared", False),
    )
    payload = serialize_history_report_to_contract(report)
    fields_param = arguments.get("fields")
    if fields_param:
        allowed = set(f.strip() for f in fields_param.split(",")) | ALWAYS_KEEP
        payload["entries"] = [
            {k: v for k, v in entry.items() if k in allowed}
            for entry in payload["entries"]
        ]
    return [TextContent(type="text", text=json.dumps(payload, indent=2))]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write)

if __name__ == "__main__":
    asyncio.run(main())

Dependency

Bash

pip install mcp

Claude Desktop / MCP client configuration

JSON

{
  "mcpServers": {
    "commit-matrix-arch-history": {
      "command": "python3",
      "args": ["backend/mcp/arch_history_server.py"],
      "cwd": "/path/to/commit-matrix"
    }
  }
}

4. File Map
Core pipeline (shared by all consumers)
File	Role
backend/cli/arch_history/orchestrator.py	Build, filter, serialize. Hosts CONTRACT_VERSION, derive_badges, serialize_history_report_to_contract, _compute_generation_boundaries
backend/cli/arch_history/models.py	Internal dataclasses: SnapshotEntry, HistoryReport, metrics, BoundaryInfo, BoundaryScope, DisplacedSnapshot
backend/cli/arch_history/taxonomy.py	Boundary layer: shape tokens, cause tags/labels, magnitude mapping
backend/cli/arch_history/data/loader.py	Ledger loading, topo mapping, commit resolution
backend/cli/arch_history/data/metrics.py	Lifespan, composition, dominance computation
backend/cli/arch_history/arch_selectors.py	Selector parsing and resolution
Consumer entry points
File	Role	Status
backend/cli/arch_history/main.py	CLI (--json, --fields, --compact)	✅ Production
backend/controllers/arch_history_controller.py	HTTP controller	❌ To be created
backend/mcp/arch_history_server.py	MCP server	❌ To be created
Tests
File	Covers	Tests
test_history_serialization_contract.py	Flags/badges, taxonomy, generation summaries, fields filtering, boundary rationale	53
test_cli_history.py	UI renderer with real dataclasses	8
test_data_transformations.py	Timeline markers, dominance math, selectors	6
test_architecture_generation_flow.py	Architecture generation smoke test	—
test_architecture_commits.py	Git-state integration tests	—
test_architecture_mutations.py	Manual mutation testing tool	—
Documentation
File	Content
docs/architecture_history_metric_contract.md	Versioned contract spec, flags/badges, metrics, boundary rationale, evolution rules
docs/api_mcp_implementation_roadmap.md	This document
5. FAQ
Contract & Serialization

Q: Where is CONTRACT_VERSION defined?
A: Module-level constant in orchestrator.py, currently "1.0". Change one line to bump.

Q: When do I bump the contract version?
A: Only when removing or renaming an existing field. Adding new fields is additive and non-breaking.

Q: Why lifespan_class instead of is_long_lived/is_short_lived?
A: They were mutually exclusive booleans. lifespan_class (enum: "long", "short", "standard") eliminates the redundancy. Internal model keeps both booleans; the serializer collapses them.

Q: Why does dominance_metrics only have 2 fields?
A: longest_streak is in lifespan_metrics, reappearance_commit_count is in composition_metrics, booleans are in flags. Only effective_commits and share_of_generation are unique to dominance.

Q: What if flags and badges disagree?
A: flags always wins. badges is derived by derive_badges(flags). Contract tests enforce the invariant.
Boundary Rationale

Q: Where does boundary data come from?
A: Three sources: (1) cause_tag/cause_label/magnitude from taxonomy.py, (2) commit and scope from the first snapshot's trigger and meta sidecar, (3) displaced from the previous generation's last entry.

Q: What if the meta sidecar is missing?
A: scope will be null. The boundary object still appears with cause, magnitude, commit, and displaced.

Q: How is magnitude determined?
A: Direct lookup from normalized cause tag via MAGNITUDE_BY_NORMALIZED_TAG in taxonomy.py. No numeric thresholds. Unknown tags default to "moderate".

Q: Why is cause_tag duplicated in boundary and on the summary?
A: Top-level cause_tag for backward compat and quick access. boundary.cause_tag for self-contained boundary objects.
--fields / ?fields=

Q: What does --fields do?
A: Filters entry-level keys in JSON output. Always includes generation and snapshot_sig. Top-level metadata unaffected.

Q: Can --fields filter generation_summaries?
A: No. It only filters within entries[]. Future revision could add top-level filtering.
HTTP Implementation

Q: Do I need new serialization logic?
A: No. Same three orchestrator functions + same field filtering. ~30 lines of routing glue.

Q: Should the endpoint cache responses?
A: Optional. Include ?fields= in cache key.
MCP Implementation

Q: What package?
A: pip install mcp. Provides Server, Tool, TextContent, stdio_server.

Q: stdio or SSE?
A: stdio for local (Claude Desktop). SSE for remote/production.

Q: What about blocking I/O?
A: Wrap build_history_report() in asyncio.to_thread().
Testing

Q: Where are the test factories?
A: test_history_serialization_contract.py has _make_entry(), _make_dominance(), full HistoryReport construction.

Q: How do I test the HTTP controller?
A: Flask test client or FastAPI TestClient. Mock build_history_report to return a fixed report.
6. Implementation Checklist
HTTP Controller

    Create backend/controllers/arch_history_controller.py
    Register route in app factory
    Add backend/tests/test_arch_history_api.py
    Test: full payload returns contract_version
    Test: ?fields=flags,badges returns only allowed keys
    Test: ?generation=3 filters correctly
    Test: boundary objects present in generation summaries

MCP Server

    pip install mcp
    Create backend/mcp/__init__.py
    Create backend/mcp/arch_history_server.py
    Add client config documentation
    Test: tools/list returns tool with correct schema
    Test: tools/call with no arguments returns full payload
    Test: tools/call with fields filters correctly
    Test: boundary objects present in response
    Wrap build_history_report in asyncio.to_thread
    