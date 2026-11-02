"""Read-only query engine over public `telemetry/v1` (the only data an agent sees)."""

from __future__ import annotations

import math
from statistics import fmean, median

from deliverytwin.agent.protocol import GaugesQuery, OrdersQuery
from deliverytwin.diagnostics.detector import bad_rate
from deliverytwin.telemetry.schema import Telemetry


def _fmt(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if isinstance(x, float):
        return f"{x:.2f}"
    return str(x)


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["\t".join(header)]
    lines += ["\t".join(_fmt(v) for v in r) for r in rows]
    return "\n".join(lines)


def run_orders_query(tel: Telemetry, q: OrdersQuery) -> tuple[str, list[dict]]:
    end = tel.observed_until
    start = q.since if q.since is not None else 0.0
    P = tel.promised_delivery_minutes
    orders = [o for o in tel.orders if o.accepted]

    def key(o):
        return {"none": "all", "zone": o.zone, "restaurant": o.restaurant}[q.group_by]

    rows, out = [], []
    w = float(q.window_minutes)
    t = start
    while t < end:
        hi = min(t + w, end)
        groups: dict[str, list] = {}
        for o in orders:
            if t <= o.created < hi:
                groups.setdefault(key(o), []).append(o)
        for g in sorted(groups):
            os_ = groups[g]
            delivered = [o.delivered - o.created for o in os_ if o.delivered is not None]
            cancelled = sum(1 for o in os_ if o.cancelled is not None)
            still_open = len(os_) - len(delivered) - cancelled
            br, n_det = bad_rate(os_, end, t, hi, P)
            open_ages = [end - o.created for o in os_
                         if o.delivered is None and o.cancelled is None]
            row = {"window_start": t, "group": g, "created": len(os_),
                   "delivered": len(delivered), "cancelled": cancelled, "open": still_open,
                   "bad_rate": br if n_det else math.nan, "determinable": n_det,
                   "p50_click_to_door": median(delivered) if delivered else math.nan,
                   "mean_open_age": fmean(open_ages) if open_ages else math.nan}
            out.append(row)
            rows.append([int(t), g, len(os_), len(delivered), cancelled, still_open,
                         row["bad_rate"], n_det, row["p50_click_to_door"],
                         row["mean_open_age"]])
        t += w
    text = _table(["window_start", "group", "created", "delivered", "cancelled", "open",
                   "bad_rate", "determinable", "p50_click_to_door", "mean_open_age"], rows)
    note = (f"(orders created per window; bad = cancelled, delivered after the {P:.0f}-min "
            f"promise, or open past it at t={end:.1f}; 'determinable' counts orders whose "
            "outcome is already known; mean_open_age = minutes open orders have waited so far)")
    return text + "\n" + note, out


def run_gauges_query(tel: Telemetry, q: GaugesQuery) -> tuple[str, list[dict]]:
    if tel.profile == "customer" or not tel.gauges:
        return "gauges are not available in this observability profile", []
    end = tel.observed_until
    start = q.since if q.since is not None else 0.0
    w = float(q.window_minutes)
    rows, out = [], []
    t = start
    while t < end:
        hi = min(t + w, end)
        sel = [g for g in tel.gauges if g.metric == q.metric and t <= g.t < hi]
        by_entity: dict[str, list[float]] = {}
        for g in sel:
            by_entity.setdefault(g.entity or "all", []).append(g.value)
        for ent in sorted(by_entity):
            v = by_entity[ent]
            out.append({"window_start": t, "entity": ent, "mean": fmean(v), "max": max(v)})
            rows.append([int(t), ent, fmean(v), max(v)])
        t += w
    return _table(["window_start", "entity", "mean", "max"], rows), out
