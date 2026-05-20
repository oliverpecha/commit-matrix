# CommitMatrix Telemetry: PLAN Scoring Engine
# Profile: Backend / API
# Acronym: true | Axes: 4 | max_score: 12
# Best for: REST/GraphQL APIs, microservices, LLM backends, FastAPI, Express, Django, gRPC services

Backend and API repositories carry implicit contracts with every caller. A silent contract break multiplies by the number of consumers — and those consumers may not discover the breakage until they hit production. The primary documentation failure is the reason a contract changed: was a field renamed due to a bug, a redesign, or a deprecation? The debt pattern is undocumented implicit contracts — endpoints that work but have no schema, no validation spec, and no error contract. Every undocumented assumption is future liability.

---

## Scoring Axes

### [P] Protection (1–3)
Input validation, auth guards, and error handling completeness — how well does this change defend the system against malformed input, unauthorized access, and partial failure?

- **1 (Unguarded):** New or changed endpoint/handler has no input validation, no auth check where one is appropriate, catches no exceptions, or performs a data mutation with no transaction boundary. One bad request can corrupt state.
- **2 (Basic):** Standard error handling present (try/catch or equivalent) but edge cases uncovered — missing schema validation on inputs, no test for the error path, or auth check present but incomplete.
- **3 (Hardened):** Full input validation, appropriate auth/authz checks, explicit error responses with correct HTTP status codes, and at least one test or assertion covering the failure path.

### [L] Liability (1–3)
Degree of contract exposure — how many callers, internal services, or external consumers could be affected by this change? API contracts are implicit dependencies that break silently.

- **1 (Internal):** Change is entirely within implementation logic. No public API surface, schema, or interface contract is altered. Other services are blind to this change.
- **2 (Contract-Adjacent):** Change adds a new optional field, modifies non-breaking response shape, or alters behavior behind an existing endpoint in a way callers may observe. Backward compatible but worth communicating.
- **3 (Breaking or Broad):** Change removes a field, renames an endpoint, alters authentication flow, changes an error response format, or modifies a shared schema. Any caller without advance notice will break.

### [A] Acuity (1–3)
Observability and debuggability — can you see what this code is doing in production? Silent failures in backend services are the most expensive failures.

- **1 (Dark):** Change adds no logging, no metrics, no tracing, and no comments on non-obvious decisions. If this code fails in production, the only signal is a user complaint.
- **2 (Partial):** Basic logging on the happy path but error branches are silent, or metrics exist but are not granular enough to distinguish failure modes.
- **3 (Instrumented):** Structured logging on both success and error paths, appropriate log levels, and any non-obvious algorithmic decision has an inline comment. Bonus: new metric, span, or alert added.

### [N] Nesting (1–3)
Cognitive complexity — how hard is this logic to reason about, review safely, and debug under pressure?

- **1 (Trivial):** Config change, route registration, dependency injection wire-up, or copy/rename. No branching logic introduced.
- **2 (Moderate):** New function or handler with straightforward linear logic, a conditional or two, standard CRUD operation, or a well-understood pattern. Reviewable in under 5 minutes by someone unfamiliar with the codebase.
- **3 (Complex):** Multi-step transformation, recursive logic, multi-condition state machine, concurrency handling, cryptographic operation, or any change requiring context from multiple parts of the codebase to review safely.

---

## Danger Flag
Set `danger_flag: true` if **L = 3 AND P = 1**.
A breaking contract change with no protective hardening — callers break, nothing catches it, nothing logs it.

---

## Debt Direction
- `"increases"` — introduces duplication, bypasses existing abstractions, hardcodes values, or removes tests
- `"neutral"` — standard incremental work following established patterns
- `"reduces"` — refactors a complex function, adds missing tests, extracts a reusable abstraction, or removes dead code

---

## Tier
Calculate `tot` as P + L + A + N. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

| tot | score_pct | tier |
|---|---|---|
| 10–12 | 83–100 | `"Critical"` |
| 7–9 | 58–75 | `"Significant"` |
| 4–6 | 33–50 | `"Routine"` |
| 3 | 25 | `"Trivial"` |

## Scoring Contract

- All axes score integer **1, 2, or 3** — no floats, no 0, no 4
- `tot` must equal the exact sum of all axis scores
- `score_pct` must equal `round(tot / max_score * 100, 1)` where `max_score = 12`
- `tier` must match the threshold table above
- `danger_flag` is derived from the specific axis combination defined in this rubric
- `debt_direction` must be one of: `"increases"` | `"neutral"` | `"reduces"`
- At least one `touches_*` boolean must be present
- Respond STRICTLY in valid JSON. No markdown, no explanation, no text outside the JSON object.


## Sample Output
```json
{
  "P": 1, "L": 3, "A": 2, "N": 2,
  "tot": 8, "score_pct": 66.7, "tier": "Significant",
  "danger_flag": true, "debt_direction": "increases",
  "touches_routes": true, "touches_models": false,
  "touches_middleware": false, "touches_auth": false,
  "touches_database": false, "touches_tests": false,
  "touches_critical": true
}
```