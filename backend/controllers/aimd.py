"""AIMD (Additive Increase Multiplicative Decrease) concurrency controller."""
import threading
import time

class AIMDController:
    def __init__(self, initial=1, min_workers=1, max_workers=6, decrease_factor=0.7, increase_step=1, success_window=1):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.current = max(self.min_workers, min(initial, self.max_workers))
        self.decrease_factor = decrease_factor
        self.increase_step = increase_step
        self.success_window = max(1, success_window)
        self.success_counter = 0
        self.lock = threading.Lock()
        self.in_flight = 0
        self.condition = threading.Condition(self.lock)

    def acquire(self):
        with self.condition:
            while self.in_flight >= self.current:
                self.condition.wait()
            self.in_flight += 1

    def release(self, success=True, congestion=True):
        with self.condition:
            self.in_flight -= 1
            self.condition.notify_all()
        
        with self.lock:
            if success:
                self.success_counter += 1
                if self.success_counter >= self.success_window:
                    self.current = min(self.max_workers, self.current + self.increase_step)
                    self.success_counter = 0
            elif congestion:
                self.success_counter = 0
                self.current = max(self.min_workers, int(self.current * self.decrease_factor))
            else:
                # Non-congestion failure (e.g. auth, bad request): release slot without penalizing concurrency
                self.success_counter = 0
