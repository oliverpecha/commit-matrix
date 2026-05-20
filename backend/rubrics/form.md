# CommitMatrix Telemetry: FORM Scoring Engine
# Profile: Library / SDK / CLI Tool
# Acronym: true | Axes: 4 | max_score: 12
# Best for: npm/pip packages, developer tools, CLI utilities, shared modules, language bindings, open-source libraries

Library repositories make promises to every project that imports them. A breaking change multiplies by the number of consumers — and those consumers may not update immediately, causing version conflicts and silent behavior changes across an entire ecosystem. The primary documentation failure is the behavioral contract of public symbols: what does this function guarantee, what does it accept, what does it return on error. Debt accumulates as untested public API surface that becomes an implicit contract — every undocumented behavior is something a consumer will rely on and that you'll be afraid to change.

---

## Scoring Axes

### [F] Footprint (1–3)
Public API surface change — is the change internal only, safely additive, or does it alter the contract that all consumers depend on?

- **1 (Internal):** Change is entirely within private implementation. No exported symbol, public function signature, CLI flag, or documented behavior is altered. Consumers are completely unaffected.
- **2 (Additive):** Change adds a new export, new CLI flag, new optional parameter, or new configuration key without removing or altering existing ones. Backward compatible by design.
- **3 (Breaking or Mutation):** Change removes an export, renames a function, changes a required parameter, alters return type, or modifies behavior of an existing CLI command. Requires a semver major bump; every consumer must adapt.

### [O] Output (1–3)
Determinism and reliability of what the function returns — unpredictable output from a library corrupts every consumer silently.

- **1 (Uncertain):** Change introduces non-determinism (timestamp-dependent behavior, system-environment assumptions), swallows errors silently, or has branching logic where one path returns an undocumented type or shape.
- **2 (Expected):** Standard implementation with predictable output following established patterns. Error cases are handled but may not cover all edge inputs.
- **3 (Proven):** Change includes or modifies tests that assert the exact output contract, handles edge inputs explicitly (null, empty, boundary values), or adds type annotations that enforce the output shape at compile time.

### [R] Regression (1–3)
How many existing capabilities could this change silently break? Libraries accumulate implicit behavioral contracts over time — even "safe" refactors can violate them.

- **1 (Isolated):** Change affects a brand new function or clearly isolated utility with no existing callers in the codebase. Regression risk is bounded to the new surface.
- **2 (Moderate):** Change modifies an existing function with known callers, alters shared logic used in multiple places, or changes parsing/serialization behavior. Manual review of callers is prudent.
- **3 (High):** Change touches a foundational utility — parser, serializer, config loader, base class — that all other modules depend on, or removes error-handling that callers may rely on. Full regression test run required before release.

### [M] Maturity (1–3)
Shipment readiness — is this commit ready to be versioned and published? Libraries require higher documentation and changelog discipline than application code because consumers have no visibility into the source.

- **1 (Incomplete):** No CHANGELOG entry, no docstring on new public symbols, no type annotations on public API, and no tests. Publishing this as-is leaves consumers guessing about behavior and contract.
- **2 (Partial):** Either tests OR documentation is present, but not both. Or: change is internal-only where reduced documentation is appropriate.
- **3 (Shippable):** New public symbols have docstrings/JSDoc, types are explicit, CHANGELOG or commit body captures the user-facing change in plain language, and tests cover the new behavior. Ready for a patch or minor release.

---

## Danger Flag
Set `danger_flag: true` if **F = 3 AND O = 1**.
A breaking API change whose output is unreliable — consumers are forced to upgrade into a function that may return unpredictably. The most damaging pattern a library can ship.

---

## Debt Direction
- `"increases"` — adds untested public API, removes existing tests, introduces untyped returns, or adds undocumented behavior
- `"neutral"` — standard incremental work following existing patterns
- `"reduces"` — adds missing tests to existing public API, adds type annotations to untyped exports, improves docstrings, or removes deprecated symbols

---

## Tier
Calculate `tot` as F + O + R + M. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "F": 3, "O": 1, "R": 2, "M": 1,
  "tot": 7, "score_pct": 58.3, "tier": "Significant",
  "danger_flag": true, "debt_direction": "increases",
  "touches_public_api": true, "touches_cli": false,
  "touches_types": true, "touches_tests": false,
  "touches_docs": false, "touches_changelog": false,
  "touches_critical": true
}
```