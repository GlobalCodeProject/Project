from collections import deque
from time import time


class IdleDetector:
    """Simple moving-average idle detector."""
    def __init__(self, threshold_w: float, duration_s: int, window: int = 5):
        self.threshold = threshold_w
        self.duration = duration_s
        self.window = window
        self.buffers = {}      # device_id -> deque[float]
        self.below_since = {}  # device_id -> float|None

    def add(self, device_id: str, watts: float) -> bool:
        buf = self.buffers.setdefault(device_id, deque(maxlen=self.window))
        buf.append(float(watts))
        avg = sum(buf) / len(buf)
        now = time()
        if avg < self.threshold:
            if self.below_since.get(device_id) is None:
                self.below_since[device_id] = now
            return (now - self.below_since[device_id]) >= self.duration
        else:
            self.below_since[device_id] = None
            return False
