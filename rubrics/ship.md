# CommitMatrix Telemetry: SHIP Scoring Engine
# Profile: Mobile / Native App
# Acronym: true | Axes: 4 | max_score: 16
# Best for: iOS (Swift/ObjC), Android (Kotlin/Java), React Native, Flutter, Expo, Capacitor, desktop Electron apps

Mobile repositories operate under a uniquely constrained deployment model — you cannot hot-patch a shipped binary. A defect in a published version reaches every user who has not updated, and app store review adds a 1–3 day lag before any fix reaches users. The blast radius multiplies by both affected users and time-until-patch. The critical documentation failure is platform-specific behavioral constraints: why does this permission request appear here, why is this API call guarded by an OS version check? Debt accumulates as minimum OS version creep, undocumented platform workarounds, and feature flags that were never cleaned up.

---

## Scoring Axes

### [S] Store (1–4)
App store compliance risk — does this change affect review guidelines, permission declarations, binary compatibility, or distribution constraints?

- **1 (Safe):** Change has no interaction with app store review criteria — pure business logic, internal utility, or UI change that does not affect permissions, entitlements, or binary metadata.
- **2 (Adjacent):** Change touches something that reviewers may scrutinize — a new third-party SDK, a UI pattern near permission prompts, or a change to app metadata — but does not violate any explicit guideline.
- **3 (Review Risk):** Change modifies permission declarations, entitlements, payment flows, content rating relevant features, or patterns explicitly prohibited or restricted by the app store review guidelines. Rejection risk is real.

### [H] Habitat (1–4)
OS and device compatibility — is this change safe across the entire supported version range and device matrix?

- **1 (Universal):** Change uses only APIs available on the minimum supported OS version, has no device-specific assumptions, and behaves consistently across screen sizes and hardware configurations.
- **2 (Guarded):** Change uses a newer API but is appropriately guarded by an OS version check. Or: change has a known device-specific behavior difference that is documented and handled.
- **3 (Fragile):** Change uses APIs without version guards, assumes specific screen dimensions or hardware capabilities, or has untested behavior on the minimum supported OS version. Could crash or silently fail on older devices.

### [I] Intent (1–4)
Platform constraint documentation — are OS-specific decisions, workarounds, and compatibility choices explained? These decisions are almost never documented and become impossible to revisit safely.

- **1 (Opaque):** No commit body. Platform-specific code added with no explanation of the underlying OS constraint, API limitation, or device quirk it addresses. Future engineers will not know whether to keep or remove this.
- **2 (Labeled):** Commit subject communicates what platform concern was addressed ("fix(ios): guard Camera API behind iOS 16 check") but the body does not explain why the constraint exists or what happens on older versions.
- **3 (Documented):** Body explains the platform constraint — the OS version that introduced the API, the device behavior being worked around, the fallback behavior on unsupported versions, and any known edge cases.

### [P] Patch (1–4)
Patchability — if this change introduces a defect, how quickly and cleanly can it be fixed given mobile deployment constraints?

- **1 (Release-locked):** Defect requires a full app store release to fix — binary change, native module update, or entitlement modification. Fix is 1–3 days away at minimum, and store rejection could extend that. Users are stuck.
- **2 (OTA-eligible):** Defect can be fixed via an over-the-air update (React Native, Expo, or equivalent OTA mechanism) without a full store release. Fast turnaround but still requires a deployment step.
- **3 (Reversible):** Change is behind a feature flag, a remote config value, or a server-driven parameter that can be toggled without any app update. Rollback is instant.

---

## Danger Flag
Set `danger_flag: true` if **S = 3 AND P = 1**.
An app store compliance risk that cannot be patched without a full release cycle — the change is in users' hands, the fix is days away, and the store may reject the corrective update. The defining worst-case pattern of mobile development.

---

## Debt Direction
- `"increases"` — adds undocumented platform workarounds, hardcodes device-specific values, skips OS version guards, or removes a feature flag in favor of a hardcoded behavior
- `"neutral"` — standard incremental work following existing patterns
- `"reduces"` — documents an existing undocumented workaround, adds a missing OS version guard, wraps a hardcoded value in remote config, or cleans up a dead feature flag

---

## Tier
Calculate `tot` as S + H + I + P. Calculate `score_pct` as `round(tot / 16 * 100, 1)`.

| tot | score_pct | tier |
|---|---|---|
| 13–16 | 81–100 | `"Pivotal"` |
| 8–12 | 50–75 | `"Core"` |
| 4–7 | 25–44 | `"Minor"` |

## Scoring Contract

- All axes score integer **1, 2, 3, or 4** — no floats, no 0, no 5
- `debt_direction` must be one of: `"increases"` | `"neutral"` | `"reduces"`
- At least one `touches_*` key must be present, scoring a 0-4 integer intensity
- Do NOT calculate or include `tot`, `score_pct`, `tier`, or `danger_flag` (these are computed by application code)
- Respond STRICTLY in valid JSON. No markdown, no explanation, no text outside the JSON object.


## Sample Output
<!-- Universal Contract: danger_flag, debt_direction, 1-4 intensity touches -->
```json
{
  "S": 3,
  "H": 2,
  "I": 1,
  "P": 1,
  "tot": 7,
  "score_pct": 58.3,
  "tier": "Core",
  "danger_flag": true,
  "debt_direction": "increases",
  "touches_permissions": 3,
  "touches_native_modules": 0,
  "touches_ui": 3,
  "touches_platform_config": 3,
  "touches_feature_flags": 0,
  "touches_tests": 0,
  "touches_critical": 3
}
```