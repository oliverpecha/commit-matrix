"""AIMD (Additive Increase Multiplicative Decrease) concurrency controller."""
import threading
import time

class AIMDController:
    def __init__(self, initial=1, max_workers=6, decrease_factor=0.5, increase_step=1):
        self.current = initial
        self.max_workers = max_workers
        self.decrease_factor = decrease_factor
        self.increase_step = increase_step
        self.lock = threading.Lock()
        self.in_flight = 0
        self.condition = threading.Condition(self.lock)

    def acquire(self):
        with self.condition:
            while self.in_flight >= self.current:
                self.condition.wait()  # Releases lock while waiting
            self.in_flight += 1

    def release(self, success=True):
        with self.condition:
            self.in_flight -= 1
            self.condition.notify_all()  # Wake all waiting threads
        
        with self.lock:
            if success:
                self.current = min(self.current + self.increase_step, self.max_workers)
            else:
                self.current = max(1, int(self.current * self.decrease_factor))
