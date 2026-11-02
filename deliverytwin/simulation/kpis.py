"""Operational KPIs computed from the event log only (RFC §5)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from deliverytwin.simulation.eventlog import EventLog


@dataclass(frozen=True)
class Kpis:
    created: int
    rejected: int
    delivered: int
    cancelled: int
    in_flight: int
    late_rate: float
    delivery_p50: float
    delivery_p95: float
    assign_delay_mean: float
    cancel_rate: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return math.nan
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def compute_kpis(log: EventLog, promised_minutes: float, window_start: float = 0.0) -> Kpis:
    """KPIs over orders created at or after `window_start`."""
    created: dict[str, float] = {}
    accepted: dict[str, float] = {}
    assigned: dict[str, float] = {}
    delivered: dict[str, float] = {}
    rejected: set[str] = set()
    cancelled: set[str] = set()
    for e in log.events:
        ev = e["ev"]
        if ev == "order_created" and e["t"] >= window_start:
            created[e["oid"]] = e["t"]
        oid = e.get("oid")
        if oid not in created:
            continue
        if ev == "order_accepted":
            accepted[oid] = e["t"]
        elif ev == "order_rejected":
            rejected.add(oid)
        elif ev == "order_assigned":
            assigned.setdefault(oid, e["t"])
        elif ev == "order_delivered":
            delivered[oid] = e["t"]
        elif ev == "order_cancelled":
            cancelled.add(oid)
    durations = [delivered[o] - created[o] for o in delivered]
    late = [d > promised_minutes for d in durations]
    delays = [assigned[o] - accepted[o] for o in assigned if o in accepted]
    n_acc = len(accepted)
    in_flight = n_acc - len(delivered) - len(cancelled)
    return Kpis(
        created=len(created),
        rejected=len(rejected),
        delivered=len(delivered),
        cancelled=len(cancelled),
        in_flight=in_flight,
        late_rate=(sum(late) / len(late)) if late else math.nan,
        delivery_p50=_quantile(durations, 0.5),
        delivery_p95=_quantile(durations, 0.95),
        assign_delay_mean=(sum(delays) / len(delays)) if delays else math.nan,
        cancel_rate=(len(cancelled) / n_acc) if n_acc else math.nan,
    )


def cohort_bad_rate(log: EventLog, promised_minutes: float, created_lo: float,
                    created_hi: float, now: float) -> tuple[float, int]:
    """Bad-order rate of a closed creation cohort, evaluated at `now`.

    Cohort: accepted orders created in [created_lo, created_hi). An order is bad if it was
    cancelled, delivered after the promise, or is still open past the promise at `now`.
    Requires now >= created_hi + promised_minutes so every cohort order is determinable;
    the denominator is then the whole cohort in every arm (no selection by outcome).
    Codex review G2.1, finding 5.
    """
    if now < created_hi + promised_minutes:
        raise ValueError("cohort not fully determinable: need now >= created_hi + promise")
    accepted: dict[str, float] = {}
    outcome: dict[str, str] = {}
    delivered_at: dict[str, float] = {}
    for e in log.events:
        if e["t"] > now:
            break
        oid = e.get("oid")
        if e["ev"] == "order_accepted" and created_lo <= e["t"] < created_hi:
            accepted[oid] = e["t"]
        elif oid in accepted and e["ev"] == "order_cancelled":
            outcome[oid] = "cancelled"
        elif oid in accepted and e["ev"] == "order_delivered":
            outcome[oid] = "delivered"
            delivered_at[oid] = e["t"]
    bad = 0
    for oid, t in accepted.items():
        o = outcome.get(oid)
        if o == "cancelled" or o is None:
            bad += 1  # cancelled, or still open although past the promise
        elif delivered_at[oid] - t > promised_minutes:
            bad += 1
    n = len(accepted)
    return (bad / n if n else math.nan), n


def cohort_penalized_time(log: EventLog, promised_minutes: float, created_lo: float,
                          created_hi: float, now: float) -> tuple[float, int]:
    """Mean click-to-door time of a closed cohort with complete follow-up.

    Delivered orders contribute their duration; cancelled or still-open orders contribute
    `now - accepted` (a penalty no smaller than any feasible duration), so a treatment
    cannot look better by pushing slow orders out of the measured set.
    Codex review G1, finding 8.
    """
    if now < created_hi + promised_minutes:
        raise ValueError("cohort not fully determinable: need now >= created_hi + promise")
    accepted: dict[str, float] = {}
    delivered_at: dict[str, float] = {}
    for e in log.events:
        if e["t"] > now:
            break
        oid = e.get("oid")
        if e["ev"] == "order_accepted" and created_lo <= e["t"] < created_hi:
            accepted[oid] = e["t"]
        elif oid in accepted and e["ev"] == "order_delivered":
            delivered_at[oid] = e["t"]
    times = [delivered_at.get(o, now) - t for o, t in accepted.items()]
    return (sum(times) / len(times) if times else math.nan), len(times)


def cohort_outcomes(log: EventLog, promised_minutes: float, created_lo: float,
                    created_hi: float, now: float) -> dict[str, tuple[bool, float]]:
    """Per-order (bad, penalized_time) for a closed, fully determinable cohort.

    bad: cancelled, delivered after the promise, or still open (hence past the promise)
    at `now`. penalized_time: delivery duration, or `now - accepted` if not delivered.
    """
    if now < created_hi + promised_minutes:
        raise ValueError("cohort not fully determinable: need now >= created_hi + promise")
    accepted: dict[str, float] = {}
    delivered: dict[str, float] = {}
    cancelled: set[str] = set()
    for e in log.events:
        if e["t"] > now:
            break
        oid = e.get("oid")
        if e["ev"] == "order_accepted" and created_lo <= e["t"] < created_hi:
            accepted[oid] = e["t"]
        elif oid in accepted and e["ev"] == "order_delivered":
            delivered[oid] = e["t"]
        elif oid in accepted and e["ev"] == "order_cancelled":
            cancelled.add(oid)
    out = {}
    for oid, t in accepted.items():
        if oid in delivered:
            d = delivered[oid] - t
            out[oid] = (d > promised_minutes, d)
        else:
            out[oid] = (True, now - t)
    return out


def demand_cohort_metrics(log: EventLog, promised_minutes: float, created_lo: float,
                          created_hi: float, now: float) -> dict:
    """Outcomes for ALL demand created in [created_lo, created_hi), accepted or rejected.

    A rejected order is an unsuccessful order (bad) with penalised time `now - created`, so
    an intervention cannot look better by turning customers away (Codex review G3).
    """
    if now < created_hi + promised_minutes:
        raise ValueError("cohort not fully determinable: need now >= created_hi + promise")
    created: dict[str, float] = {}
    rejected: set[str] = set()
    delivered: dict[str, float] = {}
    for e in log.events:
        if e["t"] > now:
            break
        oid = e.get("oid")
        if e["ev"] == "order_created" and created_lo <= e["t"] < created_hi:
            created[oid] = e["t"]
        elif oid in created and e["ev"] == "order_rejected":
            rejected.add(oid)
        elif oid in created and e["ev"] == "order_delivered":
            delivered[oid] = e["t"]
    bad, times = 0, []
    for oid, t in created.items():
        if oid in delivered:
            d = delivered[oid] - t
            bad += d > promised_minutes
            times.append(d)
        else:  # rejected, cancelled or still open past the promise
            bad += 1
            times.append(now - t)
    n = len(created)
    return {"n": n, "rejected": len(rejected),
            "bad_rate": bad / n if n else math.nan,
            "penalized_time": sum(times) / n if n else math.nan}
