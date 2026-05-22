# CommitMatrix Telemetry: CORD Scoring Engine
# Profile: Full-Stack / Mixed / Monorepo
# Acronym: true | Axes: 4 | max_score: 12
# Best for: Full-stack apps, monorepos, projects where frontend, backend, database, and infra coexist

Full-stack repositories carry failure surfaces at every layer seam. A commit that touches the database schema, the API contract, and the frontend simultaneously has three independent failure points — any one can break in isolation. The primary documentation failure is the business decision behind the change: full-stack commits encode the most consequential product decisions and are the least documented. Debt accumulates as tight cross-layer coupling with no abstraction — API calls hardcoded in components, business logic in view files, database queries in route handlers.

---

## Scoring Axes

### [C] Coupling (1–3)
How many distinct architectural layers does this commit touch simultaneously? Commits spanning multiple layers multiply review complexity and failure surface non-linearly.

- **1 (Single-layer):** Change is entirely within one layer — pure frontend, pure backend logic, or pure config. Reviewable by someone who understands only that layer.
- **2 (Two-layer):** Change spans two layers — typically backend + frontend (new endpoint + its consumer) or backend + database (migration + model update). Requires cross-layer awareness to review safely.
- **3 (Multi-layer):** Change touches three or more layers — e.g., a new feature touching a DB migration, an API handler, a frontend component, and a config update in a single commit. Each layer boundary is an independent failure point.

### [O] Openness (1–3)
Reversibility — how easily can this change be undone if it causes a production incident? In full-stack systems, some changes are one-way doors.

- **1 (Irreversible):** Change includes a destructive database migration (column drop, table rename, data transform), removes a backward-incompatible API version, or alters persistent state in a way that cannot be cleanly reverted without data loss.
- **2 (Recoverable):** Change can be reverted with a `git revert` but recovery requires additional steps — running a rollback migration, clearing a cache, notifying consumers. Not instant.
- **3 (Clean):** Change is purely additive or behavioral and can be reverted with a single `git revert` and redeploy. No persistent state, schema, or contract is permanently altered.

### [R] Resilience (1–3)
Error handling quality at every cross-layer seam introduced — in full-stack systems, the seams between layers are where failures actually happen in production.

- **1 (Brittle):** New integration point (API call, DB query, external service) added with no error handling at the boundary, no loading/error state in the UI, or no fallback if the dependency is unavailable.
- **2 (Partial):** Error handling exists on one side of the boundary — the backend returns a proper error code, but the frontend doesn't handle it gracefully. Or: optimistic UI update with no rollback on failure.
- **3 (Resilient):** Both sides of every new integration boundary handle failure explicitly — structured error responses, frontend error and loading states, and timeouts or retries considered where appropriate.

### [D] Documentation (1–3)
Quality of decision documentation — does this commit leave enough context for a future engineer to understand the business and architectural reasoning?

- **1 (Blank):** No commit body. Subject is mechanical ("update user flow", "fix bug"). The commit encodes a decision that will be completely opaque six months from now.
- **2 (Summary):** Conventional commit prefix with a meaningful subject. Body may be absent, but the subject communicates the user-facing intent clearly.
- **3 (Decision Log):** Body explains the why: what user need drove this, what alternatives were considered, any known tradeoffs. References a ticket, design doc, or prior discussion. A future engineer can reconstruct the reasoning without asking anyone.

---

## Danger Flag
Set `danger_flag: true` if **C = 3 AND O = 1**.
A multi-layer change that is irreversible — the commit touches everything and cannot be cleanly undone. The highest-risk pattern in full-stack work.

---

## Debt Direction
- `"increases"` — adds cross-layer coupling without abstraction, hardcodes values that should live in config, skips tests for new integration points
- `"neutral"` — standard incremental feature or fix work
- `"reduces"` — decouples layers, extracts a reusable integration pattern, adds missing tests for existing cross-layer flows, or simplifies a complex dependency chain

---

## Tier
Calculate `tot` as C + O + R + D. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "C": 3, "O": 1, "R": 2, "D": 2,
  "tot": 8, "score_pct": 66.7, "tier": "Significant",
  "danger_flag": true, "debt_direction": "neutral",
  "touches_frontend": true, "touches_backend": true,
  "touches_database": true, "touches_infrastructure": false,
  "touches_auth": false, "touches_tests": false,
  "touches_critical": true
}
```