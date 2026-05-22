# CommitMatrix Telemetry: WAVE Scoring Engine
# Profile: Frontend / UI
# Acronym: true | Axes: 4 | max_score: 12
# Best for: React, Vue, Svelte, Angular apps, design systems, component libraries, dashboards, static sites

Frontend repositories render directly in front of every user simultaneously. A shared component change affects every screen that uses it; a global style change affects every page. The primary documentation failure is design intent and user rationale — the diff shows pixels, never the UX reasoning. Debt accumulates as hardcoded values that should be design tokens, duplicated component logic, and accessibility shortcuts taken under deadline pressure.

---

## Scoring Axes

### [W] Width (1–3)
How much of the UI surface is affected — measures the scope of impact from a single isolated component to the global application experience.

- **1 (Local):** Change affects a single leaf-level component or a route-specific file. One screen or section is affected. A bug here is isolated to a single view.
- **2 (Shared):** Change affects a reusable component, a layout wrapper, shared state, a utility hook, or a styling token used across multiple views. A bug here degrades multiple screens.
- **3 (Global):** Change affects the design system foundation, global state management, routing logic, authentication views, or app-level configuration. Every user on every page is affected.

### [A] Access (1–3)
Accessibility and UX integrity — does this change serve all users, including those with disabilities, on constrained devices, or using assistive technology?

- **1 (Regressive):** Change removes or ignores accessibility attributes (aria-*, role, label), introduces keyboard traps, breaks focus management, uses color alone to convey meaning, or reduces touch target sizes below 44px. Or: layout change creates overflow or broken states on mobile viewports.
- **2 (Neutral):** Change does not significantly improve or degrade accessibility or UX integrity. Standard feature work that follows existing patterns without explicit a11y consideration.
- **3 (Intentional):** Change explicitly improves accessibility — adds aria attributes, improves focus flow, increases contrast ratio, adds skip navigation — or includes responsive behavior tested across viewport sizes.

### [V] Voice (1–3)
Clarity of design rationale — is the UX reasoning documented? Frontend commits are often the least documented; why a change was made is lost the moment it merges.

- **1 (Silent):** No commit body. Change is a visual diff with no explanation of design intent, user story, or UX rationale. The diff shows what pixels changed; nothing explains why.
- **2 (Labeled):** Conventional commit prefix and a clear subject line ("fix(nav): collapse mobile menu on route change"). The what is clear but the design rationale is absent.
- **3 (Reasoned):** Body includes the user-facing motivation, references a design spec, issue, or Figma link, or explains the tradeoff between competing approaches.

### [E] Economy (1–3)
Debt direction — does this commit use the design system correctly, or does it accumulate hardcoded values and duplicated logic that future changes will have to untangle?

- **1 (Wasteful):** Hardcodes color, spacing, or typography values that should be design tokens; duplicates component logic that should be extracted; removes or ignores a11y attributes under time pressure.
- **2 (Neutral):** Standard incremental feature or fix work that follows existing patterns. Neither improves nor worsens the design system's internal consistency.
- **3 (Efficient):** Extracts a reusable component, replaces hardcoded values with tokens, adds missing a11y attributes to existing elements, or deletes unused styles and components.

---

## Danger Flag
Set `danger_flag: true` if **W = 3 AND A = 1**.
A global UI change that regresses accessibility affects every user on every page simultaneously — the widest possible harm from the most invisible defect type.

---

## Debt Direction
Evaluate the **net design system debt direction** of the entire commit holistically.

- `"increases"` — The commit introduces hardcoded values, duplicated component logic, removed a11y attributes, or bypasses the design system. Future changes will need to clean this up.
- `"neutral"` — The commit is standard incremental work that follows existing patterns. Neither improves nor worsens the design system's internal consistency.
- `"reduces"` — The commit actively improves the design system: extracts a reusable component, replaces hardcoded values with tokens, adds missing a11y attributes, or deletes unused styles.

**Primary signal:** The [E] Economy axis score is your strongest indicator — E = 1 almost always means `"increases"`, E = 3 almost always means `"reduces"`. Override this only if other axes provide strong contrary evidence about the holistic debt posture of the commit.

---

## Tier
Calculate `tot` as W + A + V + E. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "W": 3, "A": 1, "V": 2, "E": 1,
  "tot": 7, "score_pct": 58.3, "tier": "Significant",
  "danger_flag": true, "debt_direction": "increases",
  "touches_components": true, "touches_state": false,
  "touches_routing": false, "touches_styles": true,
  "touches_design_system": true, "touches_tests": false,
  "touches_critical": true
}
```