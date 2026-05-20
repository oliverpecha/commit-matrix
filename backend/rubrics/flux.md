# CommitMatrix Telemetry: FLUX Scoring Engine
# Profile: Data / ML / ETL Pipeline
# Acronym: true | Axes: 4 | max_score: 12
# Best for: ETL pipelines, ML training scripts, feature engineering, data transformation, model serving, analytics backends, dbt models, Airflow DAGs

Data and ML repositories have a uniquely silent failure mode: a filter condition changed by one character can corrupt a training dataset or produce wrong model outputs, and the defect may not surface until downstream consumers notice incorrect results days or weeks later. The blast radius is every system that consumes the pipeline's output. The critical documentation failure is the data contract and transformation logic — what invariants does this transformation depend on? What are the valid input ranges? Debt accumulates as hardcoded thresholds, magic constants in feature engineering, and pipelines with no data validation step.

---

## Scoring Axes

### [F] Fidelity (1–3)
Output correctness — does this change preserve, verify, or threaten the accuracy of the data this pipeline produces?

- **1 (Unverified):** Transformation logic changed with no test asserting output correctness, no data validation step, and no before/after comparison. The output may be wrong and nothing will catch it.
- **2 (Assumed):** Change follows established patterns and is likely correct, but no explicit assertion validates the output distribution, schema, or value ranges against expected bounds.
- **3 (Validated):** Change includes or updates a test asserting output correctness — either a unit test on the transformation logic, a schema validation step, or a statistical assertion on output distribution (e.g., no nulls in required columns, value range within expected bounds).

### [L] Lineage (1–3)
Reproducibility and traceability — can the output of this pipeline be recreated exactly, and can its provenance be audited?

- **1 (Unanchored):** Training script or transformation changed with no version pin on the input data, no random seed, no snapshot reference, and no record of what changed. This result cannot be reproduced next week.
- **2 (Partial):** Some reproducibility anchors present — dependencies versioned but not input data, or random seed set but data snapshot not referenced. Reproduction is possible with effort.
- **3 (Traceable):** Change explicitly anchors all sources of non-determinism — input data version or snapshot, dependency pins, random seeds, and a commit body that describes what changed and why. This run can be reproduced exactly.

### [U] Upstream (1–3)
Consumer blast radius — how many downstream systems, models, dashboards, or services depend on what this pipeline produces?

- **1 (Isolated):** Output is consumed by a single internal job or a development-only artifact. A defect here affects one process.
- **2 (Shared):** Output feeds 2–3 downstream consumers — a model, a dashboard, and an API, for example. A defect here degrades multiple systems.
- **3 (Broad):** Output feeds many downstream consumers — a production model serving live traffic, multiple analytics dashboards, and external API consumers. A defect here corrupts every system that trusts this data.

### [X] Exposure (1–3)
Validation coverage — are bad inputs caught before they corrupt outputs? Data pipelines are only as trustworthy as their input gates.

- **1 (Open):** No input validation, schema check, or data quality assertion. Malformed, null-heavy, or out-of-range inputs flow through the pipeline and corrupt outputs silently.
- **2 (Partial):** Basic schema validation present — column types checked, required fields asserted — but semantic validation absent. A column with all values set to 0 (a common corruption pattern) would pass.
- **3 (Gated):** Comprehensive input validation: schema, type, range, null rate, and at least one semantic assertion (e.g., referential integrity, statistical distribution check). Bad input is rejected before it reaches transformation logic.

---

## Danger Flag
Set `danger_flag: true` if **U = 3 AND F = 1**.
Many downstream consumers depending on a pipeline whose output fidelity is unverified — data corruption multiplied by every system that trusts this output. The silent, cascading failure mode unique to data repos.

---

## Debt Direction
- `"increases"` — adds hardcoded thresholds, magic constants, removes validation steps, or introduces non-determinism without documentation
- `"neutral"` — standard incremental work following established patterns
- `"reduces"` — adds missing validation, replaces magic constants with config-driven values, improves reproducibility anchors, or adds lineage documentation

---

## Tier
Calculate `tot` as F + L + U + X. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "F": 1, "L": 2, "U": 3, "X": 1,
  "tot": 7, "score_pct": 58.3, "tier": "Significant",
  "danger_flag": true, "debt_direction": "increases",
  "touches_transformation": true, "touches_validation": false,
  "touches_models": true, "touches_schema": false,
  "touches_config": false, "touches_tests": false,
  "touches_critical": true
}
```