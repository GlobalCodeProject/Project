from collections import deque
from time import time
from typing import Dict, Deque, Tuple, Optional


class IdleDetector:
    """
    Simple moving-average idle detector with per-device overrides.

    We append (timestamp, watts) and compute a fixed-size moving average (last N samples).
    For MVP we keep a small window (e.g., 5 samples). Duration logic is time-based.
    """

    def __init__(self, default_threshold_w: float, default_duration_s: int, window: int = 5):
        self.default_threshold = default_threshold_w
        self.default_duration = default_duration_s
        self.window = window
        self.buffers: Dict[str, Deque[float]] = {}  # device_id -> last W samples
        self.below_since: Dict[str, Optional[float]] = {}  # device_id -> ts when avg dropped below or None
        self.overrides: Dict[str, Tuple[float, int]] = {}  # device_id -> (threshold_w, duration_s)

    def set_overrides(self, device_id: str, threshold_w: Optional[float], duration_s: Optional[int]):
        if threshold_w is None and duration_s is None:
            self.overrides.pop(device_id, None)
        else:
            th = threshold_w if threshold_w is not None else self.default_threshold
            du = duration_s if duration_s is not None else self.default_duration
            self.overrides[device_id] = (float(th), int(du))

    def _cfg(self, device_id: str) -> Tuple[float, int]:
        return self.overrides.get(device_id, (self.default_threshold, self.default_duration))

    def add(self, device_id: str, watts: float) -> bool:
        buf = self.buffers.setdefault(device_id, deque(maxlen=self.window))
        buf.append(float(watts))
        avg = sum(buf) / len(buf)
        th, du = self._cfg(device_id)
        now = time()
        if avg < th:
            if self.below_since.get(device_id) is None:
                self.below_since[device_id] = now
            elapsed = now - self.below_since[device_id]
            ready = elapsed >= du
            # DEBUG ↓↓↓
            print(f"[IdleDetector] {device_id}: avg={avg:.2f}W<th={th:.2f}W, "
                  f"elapsed={elapsed:.1f}s/{du}s, window={len(buf)}, trigger={ready}")
            return ready
        else:
            # DEBUG ↓↓↓
            print(f"[IdleDetector] {device_id}: avg={avg:.2f}W>=th={th:.2f}W, reset timer")
            self.below_since[device_id] = None
            return False
