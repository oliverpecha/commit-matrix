import os, json, sys, logging
from pathlib import Path
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from backend.services.inference.scoring_call import execute_commit_inference
from backend.controllers.aimd import AIMDController

class DummyLimits:
    def wait_if_needed(self): pass
    def record_usage(self, p, c): pass
    def update_from_headers(self, h): pass

rubric_path = Path("/app/rubrics/cord.md") if Path("/app/rubrics/cord.md").exists() else Path("rubrics/cord.md")
sys_prompt = rubric_path.read_text(encoding="utf-8")

user_prompt = """Hash: b9proof123
Date: Sep 25, 2026
Author: Dev <dev@commitmatrix.io>
Subject: feat(auth): add jwt token verification middleware
Diff:
diff --git a/backend/auth.py b/backend/auth.py
new file mode 100644
--- /dev/null
+++ b/backend/auth.py
@@ -0,0 +5 @@
+def verify_token(token: str):
+    if not token:
+        raise ValueError("Missing token")
+    return True
+"""

model_name = os.environ.get("MATRIX_MODEL", "gemini/gemini-2.5-flash-lite")
tier_strategy = os.environ.get("TIER_DISTRIBUTION", "tight_floor")
print(f"=== [PROOF B9] Live Containerized Inference ===")
print(f"Model: {model_name}")
print(f"Active TIER_DISTRIBUTION: {tier_strategy}")

res = execute_commit_inference(sys_prompt, user_prompt, model_name, DummyLimits(), AIMDController())
print("\nReturned Validated Payload:")
print(json.dumps(res, indent=2))

for k in ["C", "O", "R", "D"]:
    val = res["axes"].get(k)
    assert 1 <= val <= 4, f"Axis {k} value {val} out of bounds (1-4)"

tot = res["tot"]
score_pct = res["score_pct"]
tier = res["tier"]
rationale = res.get("rationale", "")

print(f"\nVerification Checks:")
print(f"- tot: {tot} (sum of axes: {sum(res['axes'].values())})")
print(f"- score_pct: {score_pct}% (computed: {(tot/16.0)*100:.1f}%)")
print(f"- tier: {tier} (under strategy '{tier_strategy}': Minor < 7, Core [7, 14), Pivotal >= 14)")
print(f"- rationale length: {len(rationale)} chars")

assert tot == sum(res["axes"].values()), "tot does not match sum of axes"
assert abs(score_pct - (tot / 16.0 * 100)) < 0.2, "score_pct arithmetic mismatch"
assert 7.0 <= tot < 14.0 and "CORE" in tier, f"Tier mismatch for tot {tot} under {tier_strategy}"
assert len(rationale.strip()) > 0, "Rationale must not be empty"

print("\n✅ B9 PASSED: Live provider call returned valid scores, verified arithmetic, and populated rationale.")
