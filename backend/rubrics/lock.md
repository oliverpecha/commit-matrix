# CommitMatrix Telemetry: LOCK Scoring Engine
# Profile: Security / Auth / Cryptography
# Acronym: true | Axes: 4 | max_score: 12
# Best for: Authentication services, authorization middleware, OAuth, secrets management, cryptographic libraries, JWT handling, API key systems

Security repositories operate under a uniquely asymmetric failure mode: vulnerabilities are often silent until exploited, and the damage is frequently irreversible — leaked credentials, compromised sessions, exposed user data. The blast radius is every user who authenticates through this system. The critical documentation failure is the threat model: why was this cipher chosen, what attack does this rate limit address? Security commits without threat context leave reviewers unable to verify correctness. Debt accumulates as shortcuts taken under deadline pressure: hardcoded secrets, disabled checks, overly permissive scopes, and TODO comments that become permanent.

---

## Scoring Axes

### [L] Lock (1–3)
Security posture delta — does this change tighten or loosen the security boundary? This is the only axis in CommitMatrix that scores direction: a score of 1 means the commit actively weakens security.

- **1 (Loosened):** Auth check removed or bypassed, permission scope broadened silently, cryptographic algorithm downgraded, token validity extended, or rate limit loosened. The security boundary is weaker after this commit than before.
- **2 (Unchanged):** Change does not meaningfully affect the security posture — a new internal utility, a refactor that preserves existing checks, or a UI change behind an authenticated route.
- **3 (Tightened):** Change explicitly hardens the security boundary — adds a missing auth check, upgrades a cipher, enforces stricter scope validation, reduces token lifetime, or adds a missing rate limit.

### [O] Origin (1–3)
Input trust — are new inputs from untrusted sources properly validated, sanitized, and bounded before they reach security-critical paths?

- **1 (Unvalidated):** New external input (request body, query param, header, webhook payload) accepted in a security-critical path with no sanitization, type coercion, or bounds checking. One crafted input can compromise the system.
- **2 (Partial):** Basic type validation or length checks present but semantic validation absent — e.g., a JWT is verified for format but its claims are not checked against the expected scope and audience.
- **3 (Trusted):** All new inputs are fully validated — type, range, format, and semantic correctness. Allowlist-based where possible. Input rejection returns a safe, non-leaking error response.

### [C] Clarity (1–3)
Threat documentation — is the threat model and defense rationale explained? Security decisions made without documented reasoning cannot be audited, and a future maintainer who doesn't understand the threat may inadvertently reverse it.

- **1 (Undocumented):** No commit body. The security change is made with no explanation of what attack it defends against, what the risk was, or why this specific implementation was chosen.
- **2 (Partial):** Subject line communicates that a security change was made ("fix(auth): enforce scope check on token validation") but no body explains the threat vector or the decision rationale.
- **3 (Threat-Modeled):** Body explicitly names the attack vector or vulnerability being addressed, explains why the chosen approach mitigates it, and notes any residual risk or known limitations of the fix.

### [K] Keel (1–3)
Foundational stability — how load-bearing is the component being changed? The deeper a security primitive sits in the stack, the more catastrophic a mistake becomes.

- **1 (Peripheral):** Change affects a non-critical, optional, or easily isolated security component — a utility helper, a logging decorator, an optional feature flag behind auth.
- **2 (Structural):** Change affects an important but non-foundational security component — a specific auth middleware, a single service's token handling, a feature-level permission check.
- **3 (Foundational):** Change affects a core security primitive — the primary auth layer, the cryptographic hashing implementation, the session store, the shared authorization policy, or the secrets manager integration. Every authenticated operation in the system depends on this.

---

## Danger Flag
Set `danger_flag: true` if **L = 1 AND K = 3**.
A change that weakens security posture on a foundational primitive — loosening the lock on the most load-bearing wall. The single most dangerous pattern in security work: the regression is silent, the blast radius is total, and the discovery may come from an attacker before it comes from a test.

---

## Debt Direction
- `"increases"` — hardcodes secrets, disables checks, broadens scopes without justification, or adds undocumented security workarounds
- `"neutral"` — standard incremental work that preserves existing security posture
- `"reduces"` — removes a hardcoded secret, replaces a weak primitive, adds a missing validation, tightens a scope, or documents an existing undocumented security assumption

---

## Tier
Calculate `tot` as L + O + C + K. Calculate `score_pct` as `round(tot / 12 * 100, 1)`.

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
  "L": 1, "O": 2, "C": 1, "K": 3,
  "tot": 7, "score_pct": 58.3, "tier": "Significant",
  "danger_flag": true, "debt_direction": "increases",
  "touches_auth": true, "touches_crypto": false,
  "touches_tokens": true, "touches_secrets": false,
  "touches_middleware": true, "touches_tests": false,
  "touches_critical": true
}
```