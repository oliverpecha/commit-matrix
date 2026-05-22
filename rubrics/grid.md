# CommitMatrix Telemetry: GRID Scoring Engine
# Profile: Infrastructure / DevOps
# Acronym: true | Axes: 4 | max_score: 12
# Best for: Docker, Terraform, CI/CD pipelines, proxy configs, shell scripts, VPS ops, LiteLLM, Kubernetes

Infrastructure repositories are the substrate everything else runs on. When they break, every service above them breaks simultaneously. The primary blast radius is service-level — a defect cascades through every dependent. The critical documentation failure is the operational reason behind a config change: the diff shows what changed, never why. Debt accumulates as hardcoded values, undocumented workarounds, and copy-pasted config blocks that compound until the system becomes unmaintainable.

---

## Scoring Axes

### [G] Guard (1–3)
Defensive quality — does this change protect against failure? In infrastructure, an unguarded mutation can silently break entire service stacks.

- **1 (Exposed):** Raw config mutation, service restart, or destructive operation with no validation, rollback path, health check, or fallback. A failure here fails silently and fully.
- **2 (Partial):** Change includes some defensive pattern — a conditional check, an `|| exit 1` guard, a commented rollback note, or a test stub — but not comprehensively. Happy path is covered; failure path is not.
- **3 (Defended):** Change is fully guarded. Includes at minimum one of: idempotency guarantee, explicit error handling, health check or validation step, rollback mechanism, or equivalent safety net appropriate to the change type.

### [R] Reach (1–3)
Blast radius — how many independent service or infrastructure domains does this change affect? Cross-referenced against the provided ARCHITECTURE CONTEXT.

- **1 (Contained):** Change affects a single isolated component — one script, one config block, one service's Dockerfile. A failure here is local and bounded.
- **2 (Shared):** Change touches 2–3 functional domains or a shared utility that multiple services depend on. A failure here degrades multiple paths.
- **3 (Cross-cutting):** Change affects core infrastructure topology — compose networking, routing logic, secret/env management, proxy layer, or anything that all services depend on. A failure here can bring down the entire stack.

### [I] Intent (1–3)
Clarity of operational reasoning — does the commit explain why this change was made? Infrastructure commits without intent documentation become impossible to audit during incidents.

- **1 (Opaque):** No commit body. Subject describes the diff mechanically ("update config", "fix service"). The operational trigger is absent. An engineer debugging at 2am gets nothing from this.
- **2 (Partial):** Conventional-commit formatted subject with a meaningful description. Body is absent or minimal, but the subject alone conveys the general motivation.
- **3 (Documented):** Subject is precise and body explains the operational reason — what broke, what constraint was hit, what the intended behavior is. References an issue, ticket, or prior symptom if applicable.

### [D] Debt (1–3)
Net maintainability direction — does this commit move the infrastructure toward or away from sustainability? This axis can reward positive motion.

- **1 (Accumulates):** Introduces hardcoded values, copy-pasted blocks, commented-out junk, workarounds that bypass the proper system, or undocumented magic numbers. Future maintainers will pay for this.
- **2 (Neutral):** Change is functional and clean but neither improves nor worsens the overall maintainability posture. Routine additions or tweaks that follow existing patterns.
- **3 (Reduces):** Actively removes duplication, replaces a hardcoded value with a config-driven one, adds a missing abstraction, deletes dead code, or simplifies a complex dependency chain.

---

## Danger Flag
Set `danger_flag: true` if **R = 3 AND G = 1**.
Maximum blast radius with zero defensive guard — a change that touches everything and protects nothing. The catastrophic pattern in infrastructure work.

---

## Debt Direction
Evaluate the **net maintainability direction** of the entire commit holistically.

- `"increases"` — The commit leaves the infrastructure harder to maintain than before: hardcoded values, copy-pasted blocks, undocumented workarounds, magic numbers, or bypasses of the proper system.
- `"neutral"` — The commit is functional and clean but neither improves nor worsens the overall maintainability posture. Routine work that follows existing patterns.
- `"reduces"` — The commit actively improves maintainability: removes duplication, replaces a hardcoded value with a config-driven one, adds a missing abstraction, or deletes dead code.

**Primary signal:** The [D] Debt axis score is your strongest indicator — D = 1 almost always means `"increases"`, D = 3 almost always means `"reduces"`. Override this only if other axes provide strong contrary evidence about the holistic debt posture of the commit.

---

## Tier
Calculate `tot` as G + R + I + D. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "G": 2, "R": 3, "I": 1, "D": 2,
  "tot": 8, "score_pct": 66.7, "tier": "Significant",
  "danger_flag": false, "debt_direction": "neutral",
  "touches_proxy": false, "touches_scripts": true,
  "touches_config": true, "touches_dashboard": false,
  "touches_docs": false, "touches_tests": false,
  "touches_critical": true
}
```