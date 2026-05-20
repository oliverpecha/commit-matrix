# CommitMatrix Calibration

Validation infrastructure for CommitMatrix rubrics.

## Structure

```
calibration/
├── calibrate.py              # Harness entry point
├── fixtures/
│   ├── grid/
│   │   ├── floor/            # Trivial commit — expects tot 3-4
│   │   ├── typical/          # Representative mid-complexity commit
│   │   └── adversarial/      # Looks safe, conceals danger_flag
│   ├── plan/  (same structure)
│   ├── wave/  ...
│   ├── form/  ...
│   ├── cord/  ...
│   ├── lock/  ...
│   ├── flux/  ...
│   └── ship/  ...
└── reports/                  # Written by calibrate.py on each run
```

## Each Fixture Bundle Contains

| File | Purpose |
|---|---|
| `architecture.md` | Minimal repo architecture context |
| `commit.diff` | Unified diff in standard git format |
| `expected.json` | Ground-truth output (all contract fields) |
| `meta.json` | Fixture type (`floor`/`typical`/`adversarial`) + `key_check` |

## Running the Harness

```bash
# Test all rubrics against default model
python calibration/calibrate.py --rubric all

# Test one rubric verbosely
python calibration/calibrate.py --rubric lock --verbose

# Test against a specific model
python calibration/calibrate.py --rubric all --model openai/gpt-4o

# Test all rubrics against gemini flash
python calibration/calibrate.py --rubric all --model gemini/gemini-2.0-flash
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LITELLM_BASE_URL` | `http://localhost:4000` | LiteLLM proxy base URL |
| `LITELLM_API_KEY` | `sk-1234` | LiteLLM API key |
| `RUBRICS_DIR` | `./backend/rubrics` | Path to rubric `.md` files |
| `FIXTURES_DIR` | `./calibration/fixtures` | Path to fixture bundles |
| `REPORTS_DIR` | `./calibration/reports` | Path for output reports |

## Pass Criteria

A rubric **passes** for a given model if:
- `pass_rate >= 0.80` across all 3 fixture types
- The **adversarial** fixture correctly produces `danger_flag: true`
- All fixtures pass the **universal contract** validation (tot, score_pct, tier, debt_direction, touches_*)

## Contract Checks Run on Every Response

1. All axis scores are integers 1, 2, or 3 — no floats, no 0, no 4
2. `tot` equals exact sum of axis scores
3. `score_pct` equals `round(tot / max_score * 100, 1)` where `max_score = axes × 3`
4. `tier` is one of: `Critical` / `Significant` / `Routine` / `Trivial`
5. `danger_flag` is a boolean
6. `debt_direction` is one of: `increases` / `neutral` / `reduces`
7. At least one `touches_*` boolean is present

## Adding a New Fixture

1. Create `calibration/fixtures/<rubric>/<name>/`
2. Add the four required files
3. Set `meta.json` type to `floor`, `typical`, or `adversarial`
4. If adversarial, ensure `expected.json` has `"danger_flag": true`
