from collections import deque
from time import time
from typing import Dict, Deque, Tuple


class RollingStats:
    """
    Keeps timestamped watts and computes averages over 1m, 5m, 10m windows.
    We keep a deque per device with (ts, watts) and drop old samples on read.
    """

    def __init__(self):
        self.samples: Dict[str, Deque[Tuple[float, float]]] = {}

    def add(self, device_id: str, watts: float, ts: float | None = None):
        ts = ts or time()
        buf = self.samples.setdefault(device_id, deque())
        buf.append((ts, float(watts)))
        # Soft cap to keep memory bounded (drop if more than ~2000 samples)
        if len(buf) > 2000:
            buf.popleft()

    def _avg_since(self, device_id: str, horizon_s: int) -> float | None:
        from time import time as now
        cutoff = now() - horizon_s
        buf = self.samples.get(device_id)
        if not buf:
            return None
        # Drop older than 10 minutes eagerly (largest window)
        while buf and buf[0][0] < now() - 900:
            buf.popleft()
        vals = [w for (t, w) in buf if t >= cutoff]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def stats(self, device_id: str) -> dict:
        return {
            "avg_1m_w": self._avg_since(device_id, 60),
            "avg_5m_w": self._avg_since(device_id, 300),
            "avg_10m_w": self._avg_since(device_id, 600),
        }
