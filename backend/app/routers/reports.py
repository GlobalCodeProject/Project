from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request
from sqlmodel import Session, select
from ..models import TelemetryAC, TelemetryDC
from ..config import get_settings

router = APIRouter()

@router.get("/energy")
def energy_report(request: Request, device_id: Optional[str] = None,
                  start: Optional[datetime] = None, end: Optional[datetime] = None):
    """
    Very simple report:
      - AC: sum of energy_wh deltas between first/last within range (if provided)
      - DC: integrate power_w * dt (rough estimate from samples)
    Returns kWh, cost and CO2 using env factors.
    """
    settings = get_settings()
    engine = request.app.state.engine

    total_wh = 0.0

    with Session(engine) as s:
        # AC energy from meter counters (if present)
        q = select(TelemetryAC)
        if device_id: q = q.where(TelemetryAC.device_id == device_id)
        if start: q = q.where(TelemetryAC.ts >= start)
        if end:   q = q.where(TelemetryAC.ts <= end)
        ac_rows = s.exec(q.order_by(TelemetryAC.device_id, TelemetryAC.ts)).all()

        # group by device and compute delta of energy_wh
        by_dev = {}
        for r in ac_rows:
            if r.energy_wh is None: continue
            by_dev.setdefault(r.device_id, []).append((r.ts, r.energy_wh))
        for dev, rows in by_dev.items():
            if len(rows) >= 2:
                rows.sort()
                delta = rows[-1][1] - rows[0][1]
                if delta > 0:
                    total_wh += delta

        # DC rough integration (fallback)
        qd = select(TelemetryDC)
        if device_id: qd = qd.where(TelemetryDC.device_id == device_id)
        if start: qd = qd.where(TelemetryDC.ts >= start)
        if end:   qd = qd.where(TelemetryDC.ts <= end)
        dc_rows = s.exec(qd.order_by(TelemetryDC.device_id, TelemetryDC.ts)).all()

        # trapezoidal integrate per device
        from collections import defaultdict
        dev_points = defaultdict(list)
        for r in dc_rows:
            dev_points[r.device_id].append((r.ts, r.power_w))
        for dev, points in dev_points.items():
            if len(points) < 2: continue
            points.sort()
            wh = 0.0
            for (t0, p0), (t1, p1) in zip(points, points[1:]):
                dt_h = (t1 - t0).total_seconds() / 3600.0
                wh += (p0 + p1) / 2.0 * dt_h  # trapezoid
            total_wh += wh

    kwh = total_wh / 1000.0
    return {
        "kwh": round(kwh, 3),
        "cost_usd": round(kwh * settings.tariff_usd_per_kwh, 2),
        "co2_kg": round(kwh * settings.co2_kg_per_kwh, 3),
    }
