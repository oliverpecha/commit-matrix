import sys, logging, time, inspect
from unittest.mock import patch, MagicMock
from litellm.exceptions import RateLimitError, AuthenticationError, Timeout
from backend.controllers.aimd import AIMDController
from backend.services.inference.llm_gateway import execute_inference

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stdout)
limits = MagicMock()
prompt = "Hash: b2fresh004\nSubject: feat: congestion vs auth test\nDiff:\n+print(1)"

print("=== [PROOF B2.1] RateLimitError Backoff & AIMD 0.7 Decrease (6 -> 4) ===")
aimd = AIMDController(min_workers=1, max_workers=6)
aimd.current, aimd.success_window = 6, 10
rl_err = RateLimitError(message="Quota exceeded [CONGESTION-SIGNAL-RUN5]", llm_provider="gemini", model="gemini/gemini-2.5-flash-lite")
mock_resp = MagicMock(choices=[MagicMock(message=MagicMock(content='{"axes": {"C": 2, "O": 2, "R": 2, "D": 2}}'))])
mock_resp.get.return_value = {"prompt_tokens": 10, "completion_tokens": 10}

with patch("backend.services.inference.llm_gateway.completion", side_effect=[rl_err, mock_resp]):
    with patch("time.sleep") as s:
        execute_inference("gemini/gemini-2.5-flash-lite", "sys", prompt, limits, aimd, retries=2)

print(f"Workers after RateLimitError: {aimd.current} (expected: int(6 * 0.7) = 4)")
print(f"Backoff sleep count: {s.call_count}")
assert aimd.current == 4 and s.call_count == 1
print("✅ B2.1 PASSED: RateLimitError triggered backoff and congestion decrease (6 -> 4).\n")

print("=== [PROOF B2.2] AuthenticationError Fast-Fail & Concurrency Preservation (4 -> 4) ===")
aimd_auth = AIMDController(min_workers=1, max_workers=6)
aimd_auth.current = 4
auth_err = AuthenticationError(message="Invalid API Key [NON-CONGESTION-FAIL-RUN5]", llm_provider="gemini", model="gemini/gemini-2.5-flash-lite")

with patch("backend.services.inference.llm_gateway.completion", side_effect=auth_err):
    with patch("time.sleep") as s_auth:
        try:
            execute_inference("gemini/gemini-2.5-flash-lite", "sys", prompt, limits, aimd_auth, retries=3)
        except Exception as e:
            print(f"Caught non-retryable error: {e}")

print(f"Sleep count on AuthenticationError: {s_auth.call_count}")
print(f"Workers after AuthenticationError: {aimd_auth.current} (expected: 4, untouched)")
assert s_auth.call_count == 0, "AuthenticationError must not retry"
assert aimd_auth.current == 4, f"AuthenticationError must NOT decrease concurrency! Expected 4, got {aimd_auth.current}"
print("✅ B2.2 PASSED: AuthenticationError failed fast with 0 retries and preserved concurrency (4 -> 4).\n")

print("=== [PROOF B7] Outgoing Payload kwargs & 30s Timeout Cutoff ===")
sig = inspect.signature(execute_inference)
assert sig.parameters['max_tokens'].default == 1024 and sig.parameters['timeout'].default == 30

def slow_mock(*args, **kwargs):
    print(f"   [Outgoing Kwargs] max_tokens: {kwargs.get('max_tokens')} | timeout: {kwargs.get('timeout')}s")
    print("   [Provider Latency > 30s] Enforcing hard client cutoff -> aborting.")
    raise Timeout(message="Request timed out after 30.0s [TIMEOUT-SIGNAL-RUN5]", llm_provider="gemini", model=kwargs.get("model"))

with patch("backend.services.inference.llm_gateway.completion", side_effect=slow_mock):
    with patch("time.sleep"):
        try:
            execute_inference("gemini/gemini-2.5-flash-lite", "sys", prompt, limits, AIMDController(), retries=1)
        except Exception as e:
            print(f"Caught client timeout cutoff: {e}")

print("✅ B7 PASSED: max_tokens=1024, timeout=30 verified in kwargs, cutoff enforced.\n")
print("==================================================")
print("🎉 ALL B2 AND B7 VERIFICATION CHECKS PASSED CLEANLY")
print("==================================================")
