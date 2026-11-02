"""Observational features computed only from `telemetry/v1` up to the alert.

Used by the distinguishability probe (is a pair of fault families separable from what a
profile observes?) and available to non-LLM baselines. Never reads private data.
"""

from __future__ import annotations

import math
from statistics import fmean, median, pstdev

from deliverytwin.diagnostics.detector import bad_rate
from deliverytwin.telemetry.schema import Telemetry

BASELINE = (80.0, 120.0)  # creation window; evaluated at end + promise


def _nanmean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return fmean(xs) if xs else 0.0


def customer_features(tel: Telemetry, alert_t: float) -> dict[str, float]:
    P = tel.promised_delivery_minutes
    orders = [o for o in tel.orders if o.accepted]
    f: dict[str, float] = {}
    base_rate, _ = bad_rate(orders, BASELINE[1] + P, BASELINE[0], BASELINE[1], P)
    old = P + 30.0
    for lag in (0, 15, 30):
        t = alert_t - lag
        r, n = bad_rate(orders, t, t - old, t - 10, P)
        f[f"bad_rate_lag{lag}"] = (r if n else 0.0) - (base_rate if not math.isnan(base_rate) else 0.0)
    win = [o for o in orders if alert_t - old < o.created <= alert_t - 10]
    canc = [o for o in win if o.cancelled is not None and o.cancelled <= alert_t]
    deliv = [o.delivered - o.created for o in win if o.delivered is not None and o.delivered <= alert_t]
    f["cancel_share"] = len(canc) / max(len(win), 1)
    f["delivered_p50"] = median(deliv) if deliv else 0.0
    f["delivered_p90"] = sorted(deliv)[int(0.9 * (len(deliv) - 1))] if deliv else 0.0
    # Open = no delivery or cancellation *by the alert* (Codex review G2, #6).
    f["open_share"] = sum(
        1 for o in win
        if not any(v is not None and v <= alert_t for v in (o.delivered, o.cancelled))
    ) / max(len(win), 1)
    f["demand_recent"] = sum(1 for o in tel.orders if alert_t - 30 < o.created <= alert_t)
    for level in ("zone", "restaurant"):
        rates = []
        for key in {getattr(o, level) for o in orders}:
            r, n = bad_rate([o for o in orders if getattr(o, level) == key], alert_t,
                            alert_t - old, alert_t - 10, P)
            if n >= 3:
                rates.append(r)
        f[f"{level}_bad_spread"] = pstdev(rates) if len(rates) > 1 else 0.0
        f[f"{level}_bad_max"] = max(rates) if rates else 0.0
    return f


def full_features(tel: Telemetry, alert_t: float) -> dict[str, float]:
    f = customer_features(tel, alert_t)
    if tel.profile != "full" or not tel.gauges:
        return f

    def gmean(metric, lo, hi):
        return _nanmean([g.value for g in tel.gauges if g.metric == metric and lo <= g.t <= hi])

    for m in ("couriers_online", "couriers_idle", "dispatch_queue", "orders_active"):
        b = gmean(m, *BASELINE)
        w = gmean(m, alert_t - 20, alert_t)
        f[f"{m}_shift"] = w - b
        f[f"{m}_ratio"] = w / b if b > 0 else w
    return f
