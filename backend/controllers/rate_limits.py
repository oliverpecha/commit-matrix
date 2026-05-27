"""Rate limiting controller with TPM/RPM tracking."""
import threading
import time
from collections import deque

class RateLimitsController:
    def __init__(self, target_rpm=15.0):
        self.target_rpm = target_rpm
        self.tpm_limit = None
        self.rpm_limit = None
        self.token_window = deque()
        self.request_window = deque()
        self.lock = threading.Lock()
        self.window_duration = 60

    def update_from_headers(self, headers):
        with self.lock:
            tpm = headers.get("x-ratelimit-limit-tokens")
            rpm = headers.get("x-ratelimit-limit-requests")
            if tpm:
                self.tpm_limit = int(tpm)
            if rpm:
                self.rpm_limit = int(rpm)

    def record_usage(self, prompt_tokens, completion_tokens):
        now = time.time()
        total_tokens = prompt_tokens + completion_tokens
        
        with self.lock:
            self.token_window.append((now, total_tokens))
            self.request_window.append(now)
            
            cutoff = now - self.window_duration
            while self.token_window and self.token_window[0][0] < cutoff:
                self.token_window.popleft()
            while self.request_window and self.request_window[0] < cutoff:
                self.request_window.popleft()

    def wait_if_needed(self):
        time.sleep(60.0 / self.target_rpm)
        
        with self.lock:
            if not self.tpm_limit and not self.rpm_limit:
                return
            
            now = time.time()
            cutoff = now - self.window_duration
            
            while self.token_window and self.token_window[0][0] < cutoff:
                self.token_window.popleft()
            while self.request_window and self.request_window[0] < cutoff:
                self.request_window.popleft()
            
            current_tokens = sum(t[1] for t in self.token_window)
            current_requests = len(self.request_window)
            
            if self.tpm_limit and current_tokens > 0.95 * self.tpm_limit:
                sleep_time = 10
                print(f"⚠️  TPM at 95% ({current_tokens}/{self.tpm_limit}). Sleeping {sleep_time}s...", flush=True)
                time.sleep(sleep_time)
            
            if self.rpm_limit and current_requests > 0.95 * self.rpm_limit:
                sleep_time = 10
                print(f"⚠️  RPM at 95% ({current_requests}/{self.rpm_limit}). Sleeping {sleep_time}s...", flush=True)
                time.sleep(sleep_time)
