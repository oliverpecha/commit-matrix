# CommitMatrix Rubric Authoring Guide
**Version:** 2.0
**Applies to:** All CommitMatrix rubric files (`/backend/rubrics/*.md`)
**Changelog:** v2.0 — Added `score_pct` normalization to universal contract; DRAFT profile dropped (docs quality covered by per-rubric Intent/Documentation axes); registry updated to 8 active profiles.

---

## What a Rubric Is

A rubric is a scoring contract between CommitMatrix and an LLM. It defines what dimensions of a commit matter for a specific type of repository, how to score each dimension on a 1–3 scale, and what JSON shape the LLM must return. The CommitMatrix backend is completely blind to the rubric's content — it only validates the structural shape of the JSON output. The rubric has total authority over what gets measured, how, and why.

---

## Universal Structural Contract

Every rubric, regardless of project type or axis design, must produce a JSON response satisfying this contract. The backend validates this shape on every run.

### Required Fields

| Field | Type | Constraint |
|---|---|---|
| One key per axis | integer | Value must be 1, 2, or 3 — no floats, no 0, no 4 |
| `tot` | integer | Must equal the exact sum of all axis scores |
| `score_pct` | float | Must equal `round(tot / max_score * 100, 1)` where `max_score = axes × 3` |
| `tier` | string | Must be `"Critical"` / `"Significant"` / `"Routine"` / `"Trivial"` |
| `danger_flag` | boolean | Derived from rubric-specific axis combination logic |
| `debt_direction` | string | Must be `"increases"` / `"neutral"` / `"reduces"` |
| At least one `touches_*` | boolean | Domain-specific; rubric defines which domains to track |

### Why `score_pct` Exists

`score_pct` enables cross-rubric comparison in the CommitMatrix dashboard. Without it, a GRID score of 10 (Critical) and a PLAN score of 10 (Critical) are comparable — but only because both use 4 axes. If a future rubric ever uses 3 or 5 axes, raw `tot` scores would be incomparable. `score_pct` normalizes all rubrics to a 0–100 scale regardless of axis count, making every chart and ranking that crosses rubric boundaries correct by default.

### Tier Thresholds

**4-axis rubric (max_score = 12):**

| tot | score_pct | tier |
|---|---|---|
| 10–12 | 83–100 | `"Critical"` |
| 7–9 | 58–75 | `"Significant"` |
| 4–6 | 33–50 | `"Routine"` |
| 3 | 25 | `"Trivial"` |

**5-axis rubric (max_score = 15):**

| tot | score_pct | tier |
|---|---|---|
| 13–15 | 87–100 | `"Critical"` |
| 9–12 | 60–80 | `"Significant"` |
| 5–8 | 33–53 | `"Routine"` |
| 3–4 | 20–27 | `"Trivial"` |

### Axis Count

- Minimum: **3 axes** | Maximum: **5 axes**
- Count is derived from the number of genuinely orthogonal measurement dimensions the project type requires — never from word length
- The rubric header must declare `Axes: N | max_score: N*3`

---

## The Authoring Process

### Step 1 — Project Type Characterization

Define the repository type through three lenses:

**Blast radius topology:** When a commit introduces a defect, who and what gets hurt? Is damage contained to one service, one screen, one consumer, or does it cascade across the system or all downstream users?

**Documentation failure mode:** What context is most frequently lost in this repo type? In infrastructure, the operational reason behind a config change. In libraries, the behavioral contract of a public symbol. The rubric must have an axis that fights this specific failure mode.

**Debt accumulation pattern:** What makes this type of repository rot over time? Each project type has a characteristic rot pattern. The rubric must have an axis that tracks debt direction for this specific pattern.

Write a one-paragraph characterization covering all three lenses before proceeding. This paragraph becomes the rubric's opening description.

---

### Step 2 — Failure Mode Inventory

List the 5–7 commit patterns that cause the most damage in this project type. Be specific and operational — not "bad code" but "a commit that removes an exported function without a deprecation notice and no CHANGELOG entry."

At least one failure mode must be a *silent* failure — a commit that looks safe on the surface (passes CI, small diff, conventional message) but conceals real danger.

---

### Step 3 — Axis Derivation with Orthogonality Test

For each candidate axis, complete this template:

```
Axis candidate: [working name]
What it measures: [one sentence]
Failure mode it addresses: [reference Step 2 item number]
Orthogonality check A: [scenario where this axis = 3 while another specific axis = 1]
Orthogonality check B: [scenario where another specific axis = 3 while this axis = 1]
```

If you cannot complete both orthogonality scenarios, the axis is correlated and should be merged or dropped. Two axes that always move together are one axis with extra steps.

---

### Step 4 — Axis Count Decision

Count your validated orthogonal axes. Use that exact number. Do not add an axis to reach 5. Do not drop an axis to fit a word. The count is a measurement decision, not a naming decision.

---

### Step 5 — Danger Flag Derivation

Before any naming, define the catastrophic combination. It must satisfy all three tests:

1. **Plausible:** The combination can realistically occur in a real commit in this project type
2. **Distinctive:** More dangerous than a commit that merely scores high on `tot`
3. **Non-redundant:** Fires on commits the tier system alone would not catch — a `danger_flag: true` commit must be possible with a Routine or Significant tier score

---

### Step 6a — Semantic Field Expansion

For each axis, generate a cluster of at least 10 words that could legitimately represent that axis. Cast across multiple registers: technical vocabulary, plain English, domain-specific terms, single-word metaphors. Do not prune at this stage.

---

### Step 6b — Combinatorial Word Search

Find a real English word W where:
- W has exactly N letters (N = axis count from Step 4)
- Each letter maps to one word from one axis cluster
- Each axis cluster contributes exactly one letter
- No cluster is used twice

**Mapping quality grades:**

| Grade | Definition |
|---|---|
| **Earned** | The letter's word is among the first two a person would generate for that axis concept |
| **Natural** | The connection is clear and immediate but not the very first word |
| **Valid** | The connection is real but requires a brief moment of interpretation |
| **Forced** | Requires explanation to make sense — reject |

**Acceptance threshold:** All mappings ≥ Valid; ≥ 50% Earned or Natural; zero Forced.

**Fallback:** If no word passes after testing ≥ 30 candidates, use a project-type evocative name (not an acronym). Declare `Acronym: false` in the rubric header. Axes are named independently.

---

### Step 7 — Axis Naming

- Short name: single uppercase letter (the winning letter from Step 6b)
- Full name: a noun or noun phrase of 1–3 words, unambiguous without reading the definition
- No semantic overlap with other axis names in this rubric
- No verbs — axes describe a property, not an action

---

### Step 8 — Score Level Definitions

For each axis, write exactly three score level definitions (1, 2, 3).

- Each must be specific enough that two independent reviewers agree on the score for 80%+ of real commits
- Include at least one concrete example from the project type
- The **2 (middle) score must describe a specific recognizable pattern** — not "somewhere between 1 and 3." Partial implementation, happy path covered but edge cases missed, the right structure but one key element absent.

---

### Step 9 — Calibration Estimate

Target distribution for a healthy, active repo:

| Tier | Target % |
|---|---|
| Critical | 15–25% |
| Significant | 35–45% |
| Routine | 25–35% |
| Trivial | 5–15% |

If your axis definitions do not seem likely to produce this distribution, revisit the 1/2/3 thresholds before proceeding.

---

### Step 10 — Validation Fixtures

Write exactly three fixture scenarios. Each is a bundle of:
- A minimal but structurally honest `architecture.md`
- A raw unified diff (actual format, not a prose description)
- An `expected.json` with ground-truth output
- A `key_check` field naming the single most important output field to verify

**Required fixture types:**

**Fixture 1 — Floor:** Most trivial commit possible. Must produce `tot: 3` or `tot: 4`. If it scores higher, axis floor definitions are too strict.

**Fixture 2 — Typical:** Representative mid-complexity commit. Should score in the Significant tier. Expected output should feel unsurprising.

**Fixture 3 — Adversarial:** A commit designed to look safe — small diff, conventional message, passes CI — but concealing a failure mode from Step 2. Must trigger `danger_flag: true`. If it does not, the danger flag logic is insufficient.

---

### Step 11 — Rubric File Assembly

Standard file structure:

```
# CommitMatrix Telemetry: [WORD] Scoring Engine
# Profile: [Project Type Name]
# Acronym: [true / false]
# Axes: [N] | max_score: [N*3]
# Best for: [comma-separated concrete repo type examples]

[One paragraph: project type characterization from Step 1]

---

## Scoring Axes

### [[Letter]] [Full Axis Name] (1–3)
[One sentence: what this axis measures and why it matters]

- **1 ([Label]):** [Definition + concrete example]
- **2 ([Label]):** [Definition + concrete example]
- **3 ([Label]):** [Definition + concrete example]

[Repeat for each axis]

---

## Danger Flag
Set `danger_flag: true` if [specific axis value conditions].
[One sentence explaining why this is the catastrophic pattern for this project type.]

---

## Debt Direction
- `"increases"` — [specific patterns for this project type]
- `"neutral"` — [specific patterns]
- `"reduces"` — [specific patterns]

---

## Tier
Calculate `tot` as [Axis1] + [Axis2] + ... Calculate `score_pct` as `round(tot / [max_score] * 100, 1)`.

[Tier threshold table]

## Scoring Contract
[Standard contract block — identical across all rubrics]

## Sample Output
[JSON example with all fields populated]
```

---

## Rubric Review Checklist

- [ ] All axes pass the orthogonality test (Step 3)
- [ ] Axis count matches word length (or `Acronym: false` declared)
- [ ] `score_pct` formula uses the correct `max_score` for this rubric's axis count
- [ ] Tier thresholds match the correct table (4-axis or 5-axis)
- [ ] `tot` in all sample outputs equals the sum of axis scores
- [ ] `score_pct` in all sample outputs equals `round(tot / max_score * 100, 1)`
- [ ] Danger flag satisfies all three tests from Step 5
- [ ] Score level 2 for every axis is specific, not vague middle-ground
- [ ] Calibration estimate suggests a reasonable distribution (Step 9)
- [ ] All three validation fixture types present and complete
- [ ] Fixture 3 (adversarial) triggers `danger_flag: true`
- [ ] Floor fixture produces `tot` of 3 or 4

---

## Active Rubric Registry

| Word | Profile | Axes | max_score | Danger Flag | Status |
|---|---|---|---|---|---|
| **GRID** | Infrastructure / DevOps | G · R · I · D | 12 | R=3 AND G=1 | Active |
| **PLAN** | Backend / API | P · L · A · N | 12 | L=3 AND P=1 | Active |
| **WAVE** | Frontend / UI | W · A · V · E | 12 | W=3 AND A=1 | Active |
| **FORM** | Library / SDK / CLI | F · O · R · M | 12 | F=3 AND O=1 | Active |
| **CORD** | Full-Stack / Monorepo | C · O · R · D | 12 | C=3 AND O=1 | Active |
| **LOCK** | Security / Auth / Crypto | L · O · C · K | 12 | L=1 AND K=3 | Active |
| **FLUX** | Data / ML / Pipeline | F · L · U · X | 12 | U=3 AND F=1 | Active |
| **SHIP** | Mobile / Native App | S · H · I · P | 12 | S=3 AND P=1 | Active |

**Archived:**
| Word | Profile | Reason |
|---|---|---|
| CIRSD | General / Infra (original) | Superseded by GRID; axis count mismatch, weak orthogonality |
| DRAFT | Documentation / Content | Profile dropped — docs quality covered by Intent/Documentation axes in per-repo rubrics |

---

## Versioning

Rubric files are versioned independently of the CommitMatrix application.

Format: `rubric_name_v{major}.{minor}.md`
- **Minor bump:** Clarification of axis definitions with no change to scoring behavior
- **Major bump:** Any change that would cause the same diff to score differently

A rubric version change invalidates direct `tot` comparisons with prior runs. Use `score_pct` for long-range trend analysis across rubric versions.
